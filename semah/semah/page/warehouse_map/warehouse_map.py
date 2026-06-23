# Copyright (c) 2026, Dconnex and contributors
# Warehouse Map backend - all queries parameterized (no SQL injection)

import frappe
from frappe.utils import getdate, add_days, today


@frappe.whitelist()
def get_map_data(warehouse=None, expiry_days=30):
	"""Return all bins grouped by row, with live stock summary per bin."""
	expiry_days = int(expiry_days or 30)
	expiry_limit = add_days(today(), expiry_days)

	conditions = ""
	values = []
	if warehouse:
		conditions = "WHERE b.warehouse = %s"
		values.append(warehouse)

	bins = frappe.db.sql(
		"""
		SELECT b.name, b.bin_name, b.status, b.bin_row, b.warehouse
		FROM `tabBin Name` b
		{conditions}
		ORDER BY b.bin_row, b.bin_name
		""".format(conditions=conditions),
		tuple(values),
		as_dict=True,
	)

	stock_conditions = "WHERE ibl.stored_qty > 0"
	stock_values = []
	if warehouse:
		stock_conditions += " AND ibl.warehouse = %s"
		stock_values.append(warehouse)

	stock_rows = frappe.db.sql(
		"""
		SELECT
			ibl.bin_location,
			ibl.parent AS item_code,
			i.item_name,
			ibl.stored_qty,
			ibl.reserved_qty,
			ibl.batch_no,
			ibl.expiry,
			ibl.pallet,
			ibl.sub_customer,
			i.customer_ AS customer
		FROM `tabitem bin location` ibl
		LEFT JOIN `tabItem` i ON i.name = ibl.parent
		{conditions}
		""".format(conditions=stock_conditions),
		tuple(stock_values),
		as_dict=True,
	)

	# group stock by bin
	stock_by_bin = {}
	for row in stock_rows:
		key = row.bin_location
		if not key:
			continue
		bucket = stock_by_bin.setdefault(
			key,
			{
				"total_qty": 0,
				"reserved_qty": 0,
				"items": [],
				"min_expiry": None,
				"expiring": False,
			},
		)
		bucket["total_qty"] += row.stored_qty or 0
		bucket["reserved_qty"] += row.reserved_qty or 0
		bucket["items"].append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"stored_qty": row.stored_qty,
				"reserved_qty": row.reserved_qty,
				"batch_no": row.batch_no,
				"expiry": str(row.expiry) if row.expiry else None,
				"pallet": row.pallet,
				"sub_customer": row.sub_customer,
				"customer": row.customer,
			}
		)
		if row.expiry:
			exp = getdate(row.expiry)
			if not bucket["min_expiry"] or exp < getdate(bucket["min_expiry"]):
				bucket["min_expiry"] = str(exp)
			if exp <= getdate(expiry_limit):
				bucket["expiring"] = True

	# build rows -> bins structure with computed state
	rows = {}
	summary = {"vacant": 0, "occupied": 0, "reserved": 0, "expiring": 0, "total": 0}

	for b in bins:
		stock = stock_by_bin.get(b.bin_name) or stock_by_bin.get(b.name)
		state = "vacant"
		if stock and stock["total_qty"] > 0:
			state = "occupied"
			if stock["expiring"]:
				state = "expiring"
			elif stock["reserved_qty"] > 0:
				state = "reserved"
		summary[state] += 1
		summary["total"] += 1

		row_key = b.bin_row or "Unassigned"
		rows.setdefault(row_key, []).append(
			{
				"name": b.name,
				"bin_name": b.bin_name,
				"status": b.status,
				"state": state,
				"warehouse": b.warehouse,
				"total_qty": stock["total_qty"] if stock else 0,
				"reserved_qty": stock["reserved_qty"] if stock else 0,
				"min_expiry": stock["min_expiry"] if stock else None,
				"items": stock["items"] if stock else [],
			}
		)

	return {
		"rows": [{"row": k, "bins": v} for k, v in sorted(rows.items())],
		"summary": summary,
		"expiry_days": expiry_days,
	}


@frappe.whitelist()
def get_warehouses():
	"""Warehouses that actually have bins defined."""
	return frappe.db.sql(
		"""
		SELECT DISTINCT warehouse FROM `tabBin Name`
		WHERE warehouse IS NOT NULL AND warehouse != ''
		ORDER BY warehouse
		""",
		as_dict=True,
	)


@frappe.whitelist()
def find_item_bins(item_search, warehouse=None):
	"""Return bin names containing an item matching the search text."""
	if not item_search:
		return []

	like = "%" + item_search + "%"
	conditions = ""
	values = [like, like, like]
	if warehouse:
		conditions = " AND ibl.warehouse = %s"
		values.append(warehouse)

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT ibl.bin_location
		FROM `tabitem bin location` ibl
		LEFT JOIN `tabItem` i ON i.name = ibl.parent
		WHERE ibl.stored_qty > 0
		AND (ibl.parent LIKE %s OR i.item_name LIKE %s OR ibl.batch_no LIKE %s)
		{conditions}
		""".format(conditions=conditions),
		tuple(values),
		as_dict=True,
	)
	return [r.bin_location for r in rows if r.bin_location]
