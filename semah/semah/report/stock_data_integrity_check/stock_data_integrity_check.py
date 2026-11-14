import frappe
from frappe import _
from frappe.utils import flt, getdate

DEFAULT_FROM_DATE = "2026-02-01"

CRITICAL, WARNING, INFO = "Critical", "Warning", "Info"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = getdate(filters.from_date or DEFAULT_FROM_DATE)

	data = []
	for check in CHECKS:
		if filters.check and filters.check != check["label"]:
			continue
		if check["severity"] == INFO and not filters.include_info and filters.check != check["label"]:
			continue
		for row in check["fn"](filters):
			# MariaDB can return concat() over numeric/date columns as binary depending on server collation settings.
			for key, value in row.items():
				if isinstance(value, bytes):
					row[key] = value.decode()
			row.update(check=check["label"], severity=check["severity"])
			data.append(row)

	enrich(data)
	if filters.customer:
		data = [d for d in data if d.get("customer") == filters.customer]

	severity_order = {CRITICAL: 0, WARNING: 1, INFO: 2}
	data.sort(key=lambda d: (severity_order[d["severity"]], d["check"], d.get("item_code") or ""))

	return get_columns(), data, None, None, get_summary(data)


def get_columns():
	return [
		{"label": _("Severity"), "fieldname": "severity", "fieldtype": "Data", "width": 90},
		{"label": _("Check"), "fieldname": "check", "fieldtype": "Data", "width": 230},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
		{"label": _("Bin Location"), "fieldname": "bin_location", "fieldtype": "Data", "width": 110},
		{"label": _("Reference Type"), "fieldname": "reference_doctype", "fieldtype": "Data", "width": 110},
		{"label": _("Reference"), "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 160},
		{"label": _("Ledger Qty"), "fieldname": "ledger_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Location Qty"), "fieldname": "location_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Difference"), "fieldname": "difference", "fieldtype": "Float", "width": 100},
		{"label": _("Details"), "fieldname": "details", "fieldtype": "Data", "width": 320},
	]


def get_summary(data):
	counts = {CRITICAL: 0, WARNING: 0, INFO: 0}
	for d in data:
		counts[d["severity"]] += 1
	indicators = {CRITICAL: "red", WARNING: "orange", INFO: "blue"}
	return [
		{"label": _(severity), "value": count, "indicator": indicators[severity] if count else "green", "datatype": "Int"}
		for severity, count in counts.items()
	]


def warehouse_condition(filters, column):
	if not filters.warehouse:
		return "", {}
	lft, rgt = frappe.db.get_value("Warehouse", filters.warehouse, ["lft", "rgt"])
	return (
		f" and {column} in (select name from `tabWarehouse` where lft >= %(wh_lft)s and rgt <= %(wh_rgt)s)",
		{"wh_lft": lft, "wh_rgt": rgt},
	)


def item_condition(filters, column):
	return (f" and {column} = %(item_code)s", {"item_code": filters.item_code}) if filters.item_code else ("", {})


def build(filters, wh_column=None, item_column=None):
	cond, params = "", {"from_date": filters.from_date}
	for part, values in (
		warehouse_condition(filters, wh_column) if wh_column else ("", {}),
		item_condition(filters, item_column) if item_column else ("", {}),
	):
		cond += part
		params.update(values)
	return cond, params


def location_vs_ledger_mismatch(filters):
	"""Bin-location stock (used by Stock Report Semah) must equal the stock ledger Bin per item and warehouse."""
	cond_l, params = build(filters, "l.warehouse", "l.parent")
	cond_b = build(filters, "b.warehouse", "b.item_code")[0]
	cond_s = build(filters, "s.warehouse", "s.item_code")[0]

	active_pairs = frappe.db.sql(
		f"""
		select l.parent, l.warehouse from `tabitem bin location` l
		where l.parenttype = 'Item' and l.modified >= %(from_date)s {cond_l}
		union
		select s.item_code, s.warehouse from `tabStock Ledger Entry` s
		where s.is_cancelled = 0 and s.posting_date >= %(from_date)s {cond_s}
		""",
		params,
	)
	if not active_pairs:
		return []
	active_pairs = set(active_pairs)

	location_qty = {
		(r.item_code, r.warehouse): flt(r.qty)
		for r in frappe.db.sql(
			f"""select l.parent as item_code, l.warehouse, sum(l.stored_qty) as qty
			from `tabitem bin location` l where l.parenttype = 'Item' {cond_l}
			group by l.parent, l.warehouse""",
			params,
			as_dict=1,
		)
	}
	ledger_qty = {
		(r.item_code, r.warehouse): flt(r.actual_qty)
		for r in frappe.db.sql(
			f"select b.item_code, b.warehouse, b.actual_qty from `tabBin` b where 1=1 {cond_b}",
			params,
			as_dict=1,
		)
	}

	rows = []
	for key in active_pairs:
		loc, ledger = location_qty.get(key, 0), ledger_qty.get(key, 0)
		if abs(loc - ledger) < 0.001:
			continue
		if ledger == 0:
			details = _("Stock shows in bin locations but not in the stock ledger (possible phantom stock, e.g. copied on Item duplicate or left after a deleted entry)")
		elif loc == 0:
			details = _("Stock exists in the ledger but no bin location holds it")
		else:
			details = _("Bin location total differs from stock ledger")
		rows.append(
			{
				"item_code": key[0],
				"warehouse": key[1],
				"ledger_qty": ledger,
				"location_qty": loc,
				"difference": loc - ledger,
				"details": details,
			}
		)
	return rows


def negative_stock(filters):
	cond_b, params = build(filters, "b.warehouse", "b.item_code")
	cond_l = build(filters, "l.warehouse", "l.parent")[0]
	rows = frappe.db.sql(
		f"""select b.item_code, b.warehouse, b.actual_qty as ledger_qty,
			'Negative qty in stock ledger Bin' as details
		from `tabBin` b where b.actual_qty < 0 and b.modified >= %(from_date)s {cond_b}""",
		params,
		as_dict=1,
	)
	rows += frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			'Negative stored qty in bin location' as details
		from `tabitem bin location` l
		where l.stored_qty < 0 and l.modified >= %(from_date)s {cond_l}""",
		params,
		as_dict=1,
	)
	return rows


def reserved_exceeds_stored(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			concat('Reserved ', cast(l.reserved_qty as char), ' but only ', cast(l.stored_qty as char), ' stored') as details
		from `tabitem bin location` l
		where ifnull(l.reserved_qty, 0) > l.stored_qty + 0.001 and l.modified >= %(from_date)s {cond}""",
		params,
		as_dict=1,
	)


def invalid_bin_location(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			if(ifnull(l.bin_location, '') = '', 'Stock row has no bin location', 'Bin location does not exist in Bin Name') as details
		from `tabitem bin location` l
		left join `tabBin Name` n on n.name = l.bin_location
		where l.stored_qty > 0 and n.name is null and l.modified >= %(from_date)s {cond}""",
		params,
		as_dict=1,
	)


def bin_outside_warehouse(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			nullif(l.batch_no, '') as reference_name, if(ifnull(l.batch_no, '') = '', null, 'Batch') as reference_doctype,
			concat('Bin belongs to ', n.warehouse) as details
		from `tabitem bin location` l
		join `tabBin Name` n on n.name = l.bin_location
		join `tabWarehouse` lw on lw.name = l.warehouse
		join `tabWarehouse` nw on nw.name = n.warehouse
		where l.stored_qty > 0 and l.modified >= %(from_date)s
			and lw.name != nw.name and not (lw.lft >= nw.lft and lw.rgt <= nw.rgt) {cond}""",
		params,
		as_dict=1,
	)


def batch_issues(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			l.batch_no as reference_name, 'Batch' as reference_doctype,
			case
				when ifnull(l.batch_no, '') = '' then 'Batch item stored without batch no'
				when bt.name is null then 'Batch does not exist'
				else concat('Batch belongs to item ', bt.item)
			end as details
		from `tabitem bin location` l
		join `tabItem` i on i.name = l.parent
		left join `tabBatch` bt on bt.name = l.batch_no
		where l.stored_qty > 0 and l.modified >= %(from_date)s
			and (
				(i.has_batch_no = 1 and ifnull(l.batch_no, '') = '')
				or (ifnull(l.batch_no, '') != '' and (bt.name is null or bt.item != l.parent))
			) {cond}""",
		params,
		as_dict=1,
	)


def duplicate_location_rows(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, sum(l.stored_qty) as location_qty,
			nullif(l.batch_no, '') as reference_name, if(ifnull(l.batch_no, '') = '', null, 'Batch') as reference_doctype,
			concat(cast(count(*) as char), ' rows for the same item, bin and batch') as details
		from `tabitem bin location` l
		where l.stored_qty > 0 and l.modified >= %(from_date)s {cond}
		group by l.parent, l.warehouse, l.bin_location, nullif(l.batch_no, '')
		having count(*) > 1""",
		params,
		as_dict=1,
	)


def bin_status_mismatch(filters):
	cond_n, params = build(filters, "n.warehouse")
	cond_l = build(filters, "l.warehouse", "l.parent")[0]
	rows = frappe.db.sql(
		f"""select n.name as bin_location, n.warehouse, 'Bin Name' as reference_doctype, n.name as reference_name,
			sum(l.stored_qty) as location_qty, 'Bin marked Vacant but holds stock' as details
		from `tabBin Name` n
		join `tabitem bin location` l on l.bin_location = n.name and l.stored_qty > 0
		where n.status = 'Vacant' and l.modified >= %(from_date)s {cond_l}
		group by n.name, n.warehouse""",
		params,
		as_dict=1,
	)
	if filters.item_code:
		return rows
	rows += frappe.db.sql(
		f"""select n.name as bin_location, n.warehouse, 'Bin Name' as reference_doctype, n.name as reference_name,
			concat('Bin marked ', n.status, ' but holds no stock') as details
		from `tabBin Name` n
		where n.status in ('Occupied', 'Partially Occupied') and n.modified >= %(from_date)s {cond_n}
			and not exists (
				select 1 from `tabitem bin location` l where l.bin_location = n.name and l.stored_qty > 0
			)""",
		params,
		as_dict=1,
	)
	return rows


def wrong_uom_conversion(filters):
	"""A transaction UOM different from stock UOM with factor 1 means qty was booked 1:1 in the wrong unit."""
	cond, params = build(filters, "ifnull(d.t_warehouse, d.s_warehouse)", "d.item_code")
	return frappe.db.sql(
		f"""select d.item_code, ifnull(d.t_warehouse, d.s_warehouse) as warehouse,
			'Stock Entry' as reference_doctype, d.parent as reference_name, d.transfer_qty as ledger_qty,
			concat('Row ', cast(d.idx as char), ': UOM ', d.uom, ' vs stock UOM ', d.stock_uom, ' with conversion factor 1') as details
		from `tabStock Entry Detail` d
		join `tabStock Entry` se on se.name = d.parent
		where d.docstatus = 1 and d.uom != d.stock_uom and d.conversion_factor = 1
			and se.posting_date >= %(from_date)s {cond}""",
		params,
		as_dict=1,
	)


def disabled_item_with_stock(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, sum(l.stored_qty) as location_qty,
			'Disabled item still has stock in bin locations' as details
		from `tabitem bin location` l
		join `tabItem` i on i.name = l.parent
		where i.disabled = 1 and l.stored_qty > 0
			and (i.modified >= %(from_date)s or l.modified >= %(from_date)s) {cond}
		group by l.parent, l.warehouse""",
		params,
		as_dict=1,
	)


def expired_stock(filters):
	cond, params = build(filters, "l.warehouse", "l.parent")
	return frappe.db.sql(
		f"""select l.parent as item_code, l.warehouse, l.bin_location, l.stored_qty as location_qty,
			l.batch_no as reference_name, if(ifnull(l.batch_no, '') = '', null, 'Batch') as reference_doctype,
			concat('Expired on ', cast(l.expiry as char)) as details
		from `tabitem bin location` l
		where l.stored_qty > 0 and l.expiry < curdate() and l.expiry >= %(from_date)s {cond}""",
		params,
		as_dict=1,
	)


def duplicate_items(filters):
	cond, params = build(filters, item_column="i.name")
	return frappe.db.sql(
		f"""select i.name as item_code, i.item_name, i.customer_ as customer,
			concat('Same name and customer as ', group_concat(o.name separator ', ')) as details
		from `tabItem` i
		join `tabItem` o on o.item_name = i.item_name and ifnull(o.customer_, '') = ifnull(i.customer_, '')
			and o.name != i.name and o.disabled = 0
		where i.disabled = 0 and i.creation >= %(from_date)s {cond}
		group by i.name, i.item_name, i.customer_""",
		params,
		as_dict=1,
	)


CHECKS = [
	{"label": "Location vs Ledger Qty Mismatch", "severity": CRITICAL, "fn": location_vs_ledger_mismatch},
	{"label": "Negative Stock", "severity": CRITICAL, "fn": negative_stock},
	{"label": "Invalid Bin Location", "severity": CRITICAL, "fn": invalid_bin_location},
	{"label": "Batch Issues", "severity": CRITICAL, "fn": batch_issues},
	{"label": "Wrong UOM Conversion", "severity": CRITICAL, "fn": wrong_uom_conversion},
	{"label": "Reserved Qty Exceeds Stored", "severity": WARNING, "fn": reserved_exceeds_stored},
	{"label": "Bin Outside Item Warehouse", "severity": WARNING, "fn": bin_outside_warehouse},
	{"label": "Duplicate Location Rows", "severity": WARNING, "fn": duplicate_location_rows},
	{"label": "Bin Status Mismatch", "severity": WARNING, "fn": bin_status_mismatch},
	{"label": "Disabled Item With Stock", "severity": WARNING, "fn": disabled_item_with_stock},
	{"label": "Expired Stock", "severity": INFO, "fn": expired_stock},
	{"label": "Possible Duplicate Items", "severity": INFO, "fn": duplicate_items},
]


def enrich(data):
	items = {d["item_code"] for d in data if d.get("item_code")}
	if not items:
		return
	info = {
		r.name: r
		for r in frappe.get_all("Item", filters={"name": ["in", list(items)]}, fields=["name", "item_name", "customer_"])
	}
	for d in data:
		item = info.get(d.get("item_code"))
		if item:
			d.setdefault("item_name", item.item_name)
			d.setdefault("customer", item.customer_)

