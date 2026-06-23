# Copyright (c) 2026, Dconnex and contributors
# Customer Portal API - every endpoint scoped to the logged-in user's Customer.
# All SQL parameterized.

import frappe
from frappe import _
from frappe.utils import flt, nowdate, getdate


def get_customer_for_user(user=None):
	"""Resolve the Customer linked to the logged-in website user.
	Priority: Contact dynamic link -> Customer.email match.
	"""
	user = user or frappe.session.user
	if user == "Guest":
		frappe.throw(_("Please login to access the portal."), frappe.PermissionError)

	# 1. via Contact -> Dynamic Link
	customer = frappe.db.sql(
		"""
		SELECT dl.link_name
		FROM `tabContact` c
		INNER JOIN `tabDynamic Link` dl
			ON dl.parent = c.name
			AND dl.parenttype = 'Contact'
			AND dl.link_doctype = 'Customer'
		WHERE c.user = %s
		LIMIT 1
		""",
		(user,),
	)
	if customer:
		return customer[0][0]

	# 2. fallback: Customer.email custom field equals login email
	customer = frappe.db.get_value("Customer", {"email": user}, "name")
	if customer:
		return customer

	frappe.throw(
		_("Your login is not linked to any Customer. Please contact the warehouse team."),
		frappe.PermissionError,
	)


@frappe.whitelist()
def get_portal_context():
	"""Customer name + summary numbers for the portal header."""
	customer = get_customer_for_user()
	customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer

	totals = frappe.db.sql(
		"""
		SELECT
			COUNT(DISTINCT ibl.parent) AS items,
			COALESCE(SUM(ibl.stored_qty), 0) AS qty,
			COALESCE(SUM(ibl.reserved_qty), 0) AS reserved
		FROM `tabitem bin location` ibl
		INNER JOIN `tabItem` i ON i.name = ibl.parent
		WHERE i.customer_ = %s AND ibl.stored_qty > 0
		""",
		(customer,),
		as_dict=True,
	)[0]

	expiring = frappe.db.sql(
		"""
		SELECT COUNT(*) FROM `tabitem bin location` ibl
		INNER JOIN `tabItem` i ON i.name = ibl.parent
		WHERE i.customer_ = %s AND ibl.stored_qty > 0
		AND ibl.expiry IS NOT NULL
		AND ibl.expiry <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
		""",
		(customer,),
	)[0][0]

	open_requests = frappe.db.count(
		"Delivery Request",
		{"customer": customer, "doc_status": ("not in", ["Completed", "Cancelled"])},
	)

	return {
		"customer": customer,
		"customer_name": customer_name,
		"total_items": totals.items,
		"total_qty": flt(totals.qty),
		"reserved_qty": flt(totals.reserved),
		"expiring_count": expiring,
		"open_requests": open_requests,
	}


@frappe.whitelist()
def get_my_stock(search=None):
	"""Live bin-level stock for the logged-in customer only."""
	customer = get_customer_for_user()

	conditions = ""
	values = [customer]
	if search:
		like = "%" + search + "%"
		conditions = " AND (ibl.parent LIKE %s OR i.item_name LIKE %s OR ibl.batch_no LIKE %s)"
		values += [like, like, like]

	rows = frappe.db.sql(
		"""
		SELECT
			ibl.parent AS item_code,
			i.item_name,
			i.sku,
			ibl.warehouse,
			ibl.bin_location,
			ibl.pallet,
			ibl.batch_no,
			ibl.expiry,
			ibl.stored_qty,
			COALESCE(ibl.reserved_qty, 0) AS reserved_qty,
			(ibl.stored_qty - COALESCE(ibl.reserved_qty, 0)) AS available_qty,
			ibl.sub_customer
		FROM `tabitem bin location` ibl
		INNER JOIN `tabItem` i ON i.name = ibl.parent
		WHERE i.customer_ = %s AND ibl.stored_qty > 0
		{conditions}
		ORDER BY i.item_name, ibl.expiry
		""".format(conditions=conditions),
		tuple(values),
		as_dict=True,
	)

	for r in rows:
		r.expiry = str(r.expiry) if r.expiry else None
	return rows


@frappe.whitelist()
def get_my_items():
	"""Items belonging to this customer, with total available qty (for the request form)."""
	customer = get_customer_for_user()
	return frappe.db.sql(
		"""
		SELECT
			i.name AS item_code,
			i.item_name,
			i.stock_uom AS uom,
			COALESCE(SUM(ibl.stored_qty - COALESCE(ibl.reserved_qty, 0)), 0) AS available_qty
		FROM `tabItem` i
		LEFT JOIN `tabitem bin location` ibl ON ibl.parent = i.name AND ibl.stored_qty > 0
		WHERE i.customer_ = %s AND i.disabled = 0
		GROUP BY i.name, i.item_name, i.stock_uom
		HAVING available_qty > 0
		ORDER BY i.item_name
		""",
		(customer,),
		as_dict=True,
	)


@frappe.whitelist()
def create_delivery_request(required_date, items, note=None):
	"""Create a Delivery Request from the portal.
	items: JSON list [{item_code, qty}]
	"""
	import json

	customer = get_customer_for_user()

	if isinstance(items, str):
		items = json.loads(items)
	if not items:
		frappe.throw(_("Please add at least one item."))
	if not required_date:
		frappe.throw(_("Required date is mandatory."))
	if getdate(required_date) < getdate(nowdate()):
		frappe.throw(_("Required date cannot be in the past."))

	# validate ownership + availability
	clean_items = []
	for row in items:
		item_code = (row.get("item_code") or "").strip()
		qty = flt(row.get("qty"))
		if not item_code or qty <= 0:
			continue

		owner = frappe.db.get_value("Item", item_code, "customer_")
		if owner != customer:
			frappe.throw(_("Item {0} does not belong to your account.").format(item_code))

		available = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(stored_qty - COALESCE(reserved_qty, 0)), 0)
			FROM `tabitem bin location`
			WHERE parent = %s AND stored_qty > 0
			""",
			(item_code,),
		)[0][0]

		if qty > flt(available):
			frappe.throw(
				_("Only {0} available for item {1}, you requested {2}.").format(
					flt(available), item_code, qty
				)
			)
		clean_items.append({"item_code": item_code, "qty": qty})

	if not clean_items:
		frappe.throw(_("Please add at least one valid item with quantity."))

	customer_warehouse = frappe.db.get_value("Customer", customer, "customer_warehouse")

	doc = frappe.new_doc("Delivery Request")
	doc.naming_series = "DR.#####"
	doc.customer = customer
	doc.required_date = required_date
	doc.requested_date = nowdate()
	doc.doc_status = "Draft"
	if customer_warehouse:
		doc.warehouse = customer_warehouse
	if note:
		doc.title = note[:140]

	total = 0
	for row in clean_items:
		item_name = frappe.db.get_value("Item", row["item_code"], "item_name")
		uom = frappe.db.get_value("Item", row["item_code"], "stock_uom")
		doc.append(
			"item_grid",
			{
				"item_code": row["item_code"],
				"item_name": item_name,
				"qty_required": row["qty"],
				"required_date": required_date,
				"uom": uom,
			},
		)
		total += row["qty"]

	doc.total_qty = total
	doc.flags.ignore_permissions = True  # portal users have no desk role
	doc.insert()

	frappe.db.commit()
	return {"name": doc.name, "total_qty": total}


@frappe.whitelist()
def get_my_requests(limit=25):
	"""Recent delivery requests for this customer."""
	customer = get_customer_for_user()
	limit = min(int(limit or 25), 100)

	rows = frappe.db.sql(
		"""
		SELECT name, required_date, requested_date, doc_status, total_qty, creation
		FROM `tabDelivery Request`
		WHERE customer = %s
		ORDER BY creation DESC
		LIMIT %s
		""",
		(customer, limit),
		as_dict=True,
	)
	for r in rows:
		r.required_date = str(r.required_date) if r.required_date else None
		r.requested_date = str(r.requested_date) if r.requested_date else None
		r.creation = str(r.creation)

		items = frappe.db.sql(
			"""
			SELECT item_code, item_name, qty_required
			FROM `tabItem Grid`
			WHERE parent = %s AND parenttype = 'Delivery Request'
			ORDER BY idx
			""",
			(r.name,),
			as_dict=True,
		)
		r["items"] = items
	return rows
