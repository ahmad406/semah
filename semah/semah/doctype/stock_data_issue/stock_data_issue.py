import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from semah.semah.report.stock_data_integrity_check.stock_data_integrity_check import (
	CHECKS,
	DEFAULT_FROM_DATE,
	execute as run_integrity_checks,
)

CLEAR_PHANTOM = "Clear Phantom Location Stock"
UPDATE_BIN_STATUS = "Update Bin Status"

ISSUE_FIELDS = (
	"check", "severity", "item_code", "item_name", "customer", "warehouse", "bin_location",
	"reference_doctype", "reference_name", "ledger_qty", "location_qty", "difference", "details",
)


class StockDataIssue(Document):
	pass


def get_fix_action(row):
	if row.get("check") == "Location vs Ledger Qty Mismatch" and not flt(row.get("ledger_qty")):
		return CLEAR_PHANTOM
	if row.get("check") == "Bin Status Mismatch":
		return UPDATE_BIN_STATUS
	return None


def make_issue_key(row):
	parts = [row.get(f) or "" for f in ("check", "item_code", "warehouse", "bin_location", "reference_name")]
	if row.get("check") == "Wrong UOM Conversion":
		parts.append((row.get("details") or "").split(":")[0])
	return "|".join(parts)


def check_permission():
	if not frappe.has_permission("Stock Data Issue", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def scan(from_date=None, include_info=0):
	check_permission()
	from_date = from_date or DEFAULT_FROM_DATE
	include_info = int(include_info or 0)
	rows = run_integrity_checks({"from_date": from_date, "include_info": include_info})[1]

	now = now_datetime()
	scanned_checks = [c["label"] for c in CHECKS if include_info or c["severity"] != "Info"]
	existing = {
		d.issue_key: d
		for d in frappe.get_all(
			"Stock Data Issue",
			filters={"check": ["in", scanned_checks]},
			fields=["name", "issue_key", "status"],
		)
	}

	created = reopened = 0
	seen = set()
	for row in rows:
		key = make_issue_key(row)
		if key in seen:
			continue
		seen.add(key)
		values = {f: row.get(f) for f in ISSUE_FIELDS}
		for qty_field in ("ledger_qty", "location_qty", "difference"):
			values[qty_field] = flt(values[qty_field])
		values.update(fix_action=get_fix_action(row), last_seen_on=now)

		current = existing.get(key)
		if not current:
			frappe.get_doc(
				{"doctype": "Stock Data Issue", "issue_key": key, "status": "Open", "detected_on": now, **values}
			).insert(ignore_permissions=True)
			created += 1
			continue
		if current.status == "Ignored":
			continue
		if current.status == "Fixed":
			values.update(status="Open", resolution_notes=_("Detected again on scan {0}").format(now))
			reopened += 1
		frappe.db.set_value("Stock Data Issue", current.name, values)

	auto_closed = 0
	for key, d in existing.items():
		if d.status == "Open" and key not in seen:
			frappe.db.set_value(
				"Stock Data Issue",
				d.name,
				{"status": "Fixed", "fixed_on": now, "resolution_notes": _("No longer detected on scan")},
			)
			auto_closed += 1

	frappe.db.commit()
	return {"found": len(seen), "created": created, "reopened": reopened, "auto_closed": auto_closed}


@frappe.whitelist()
def clear_issues(statuses, before_date=None):
	frappe.only_for("System Manager")
	statuses = json.loads(statuses) if isinstance(statuses, str) else statuses
	statuses = [s for s in statuses or [] if s in ("Open", "Fixed", "Ignored")]
	if not statuses:
		frappe.throw(_("Select at least one status"))

	filters = {"status": ["in", statuses]}
	if before_date:
		filters["last_seen_on"] = ["<", before_date]
	count = frappe.db.count("Stock Data Issue", filters)
	frappe.db.delete("Stock Data Issue", filters)
	frappe.db.commit()
	return count


@frappe.whitelist()
def apply_fix(name):
	check_permission()
	return _apply_fix(frappe.get_doc("Stock Data Issue", name))


@frappe.whitelist()
def apply_fixes(names=None, check=None):
	"""Fix the selected records, or every open fixable record of one check type."""
	check_permission()
	if names:
		names = json.loads(names) if isinstance(names, str) else names
	elif check:
		names = frappe.get_all(
			"Stock Data Issue",
			filters={"check": check, "status": "Open", "fix_action": ["is", "set"]},
			pluck="name",
		)
	else:
		frappe.throw(_("Select records or a check type"))

	fixed, failed = 0, []
	for name in names:
		try:
			_apply_fix(frappe.get_doc("Stock Data Issue", name))
			frappe.db.commit()
			fixed += 1
		except Exception as e:
			frappe.db.rollback()
			failed.append(f"{name}: {frappe.utils.strip_html(str(e))}")
	return {"fixed": fixed, "failed": failed}


@frappe.whitelist()
def set_status(names, status, notes=None):
	check_permission()
	if status not in ("Open", "Ignored"):
		frappe.throw(_("Invalid status"))
	names = json.loads(names) if isinstance(names, str) else names
	for name in names:
		values = {"status": status, "resolution_notes": notes}
		if status == "Ignored":
			values.update(fixed_by=frappe.session.user, fixed_on=now_datetime())
		else:
			values.update(fixed_by=None, fixed_on=None)
		frappe.db.set_value("Stock Data Issue", name, values)
	return len(names)


def _apply_fix(issue):
	if issue.status != "Open":
		frappe.throw(_("{0} is not Open").format(issue.name))
	if issue.fix_action == CLEAR_PHANTOM:
		notes = clear_phantom_location_stock(issue)
	elif issue.fix_action == UPDATE_BIN_STATUS:
		notes = update_bin_status(issue.bin_location)
	else:
		frappe.throw(_("{0}: no automatic fix for {1}, fix it manually").format(issue.name, issue.check))

	issue.db_set(
		{"status": "Fixed", "fixed_by": frappe.session.user, "fixed_on": now_datetime(), "resolution_notes": notes}
	)
	return notes


def clear_phantom_location_stock(issue):
	ledger = frappe.db.sql(
		"""select count(*) as entries, ifnull(sum(actual_qty), 0) as qty from `tabStock Ledger Entry`
		where item_code = %s and warehouse = %s and is_cancelled = 0""",
		(issue.item_code, issue.warehouse),
		as_dict=1,
	)[0]
	bin_qty = flt(frappe.db.get_value("Bin", {"item_code": issue.item_code, "warehouse": issue.warehouse}, "actual_qty"))
	if abs(flt(ledger.qty)) > 0.001 or abs(bin_qty) > 0.001:
		frappe.throw(
			_("{0}: stock ledger has stock for {1} in {2} (ledger qty {3}, bin qty {4}), not clearing").format(
				issue.name, issue.item_code, issue.warehouse, flt(ledger.qty), bin_qty
			)
		)

	item = frappe.get_doc("Item", issue.item_code)
	cleared_qty, bins = 0, set()
	for row in item.get("bin") or []:
		if row.warehouse == issue.warehouse and (flt(row.stored_qty) or flt(row.reserved_qty)):
			cleared_qty += flt(row.stored_qty)
			bins.add(row.bin_location)
			row.stored_qty = 0
			row.reserved_qty = 0
	if not bins:
		return _("Nothing to clear, location stock already 0")

	item.add_comment(
		"Comment",
		_("Cleared phantom bin-location stock {0} in {1} via {2}. No stock ledger exists for it.").format(
			cleared_qty, issue.warehouse, issue.name
		),
	)
	item.save(ignore_permissions=True)

	for bin_name in bins:
		if bin_name:
			update_bin_status(bin_name)
	return _("Cleared {0} from {1} bin location(s): {2}").format(cleared_qty, len(bins), ", ".join(sorted(b for b in bins if b)))


def update_bin_status(bin_name):
	if not frappe.db.exists("Bin Name", bin_name):
		frappe.throw(_("Bin {0} does not exist").format(bin_name))

	rows = frappe.db.sql(
		"""select pallet, sum(stored_qty) as qty from `tabitem bin location`
		where bin_location = %s and stored_qty > 0 group by pallet""",
		bin_name,
		as_dict=1,
	)
	total_qty = sum(flt(r.qty) for r in rows)
	pallet = next((r.pallet for r in rows if r.pallet), None)
	capacity = flt(frappe.db.get_value("Pallet", pallet, "capacity")) if pallet else 0

	# Same rule as Stock Entry / Delivery Note bin updates: compare stored qty with pallet capacity.
	if total_qty <= 0:
		status = "Vacant"
	elif capacity and total_qty >= capacity:
		status = "Occupied"
	else:
		status = "Partially Occupied"

	old_status = frappe.db.get_value("Bin Name", bin_name, "status")
	frappe.db.set_value("Bin Name", bin_name, "status", status)
	return _("Bin {0} status {1} -> {2} (stored {3})").format(bin_name, old_status, status, total_qty)
