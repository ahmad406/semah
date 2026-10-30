# Copyright (c) 2026, Dconnex and contributors
# Mobile scan API — all SQL parameterized, all endpoints scoped to session user's roles.
# Place at: semah/semah/semah/api/scan.py

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime
from semah.semah.utils.bin_hold import assert_bin_not_held, get_hold_info


def _assert_stock_role():
	allowed = {'Stock User', 'Stock Manager', 'System Manager', 'Warehouse Manager'}
	if not allowed & set(frappe.get_roles()):
		frappe.throw(_("Access denied."), frappe.PermissionError)


# ─── 1. PON list ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_pons_for_scanning():
	"""Return open Preparation Order Notes (excluding Completed/Cancelled)."""
	try:
		_assert_stock_role()
		pons = frappe.db.sql(
			"""
			SELECT
				p.name,
				p.customer,
				p.sub_customer,
				p.order_status,
				p.required_date,
				p.allow_delivery,
				p.actual_qty,
				p.scanned_qty,
				p.total_quantity,
				c.customer_name,
				(SELECT COUNT(*) FROM `tabPreparation Storage Details` s
				 WHERE s.parent = p.name) AS item_count
			FROM `tabPreparation Order Note` p
			LEFT JOIN `tabCustomer` c ON c.name = p.customer
			WHERE p.order_status NOT IN ('Completed', 'Cancelled')
			AND p.docstatus = 1
			ORDER BY p.modified DESC
			LIMIT 100
			""",
			as_dict=True,
		)
		return pons
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Scan API: get_pons_for_scanning failed")
		raise


# ─── 2. Full scan data for one PON ───────────────────────────────────────────

@frappe.whitelist()
def get_pon_scan_data(pon_name):
	"""Return PON header + storage_details to scan + already scanned items."""
	try:
		_assert_stock_role()
		if not pon_name:
			frappe.throw(_("pon_name is required."))

		pon = frappe.db.get_value(
			"Preparation Order Note",
			pon_name,
			[
				"name", "customer", "sub_customer", "order_status",
				"required_date", "allow_delivery", "actual_qty",
				"scanned_qty", "total_quantity", "note",
			],
			as_dict=True,
		)
		if not pon:
			frappe.throw(_("Preparation Order Note {0} not found.").format(pon_name))

		pon["customer_name"] = (
			frappe.db.get_value("Customer", pon.customer, "customer_name") or pon.customer
		)

		storage = frappe.db.sql(
			"""
			SELECT
				s.name,
				s.item,
				s.item_name,
				s.bin_location_name,
				s.pallet,
				s.batch_no,
				s.delivery_qty,
				s.expiry_date,
				s.warehouse,
				s.sub_customer,
				s.uom
			FROM `tabPreparation Storage Details` s
			WHERE s.parent = %s AND s.parenttype = 'Preparation Order Note'
			ORDER BY s.idx
			""",
			(pon_name,),
			as_dict=True,
		)

		scanned = frappe.db.sql(
			"""
			SELECT
				sc.name,
				sc.bin_location_name,
				sc.pallet,
				sc.batch_no,
				sc.delivery_qty
			FROM `tabPreparation Storage Details barcode` sc
			WHERE sc.parent = %s AND sc.parenttype = 'Preparation Order Note'
			ORDER BY sc.idx
			""",
			(pon_name,),
			as_dict=True,
		)

		return {
			"pon": pon,
			"storage_details": storage,
			"scanned_items": scanned,
		}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: get_pon_scan_data failed for {pon_name}")
		raise


# ─── 3. Record one scan ───────────────────────────────────────────────────────

@frappe.whitelist()
def submit_scan(pon_name=None, row_name=None, delivery_qty=None):
	"""Add or update a scanned entry. Matches by bin + batch + pallet."""
	try:
		_assert_stock_role()

		pon_name     = pon_name     or frappe.form_dict.get('pon_name')
		row_name     = row_name     or frappe.form_dict.get('row_name')
		delivery_qty = delivery_qty if delivery_qty is not None \
		               else frappe.form_dict.get('delivery_qty', 0)

		if not pon_name:
			frappe.throw(_("pon_name is required."))
		if not row_name:
			frappe.throw(_("row_name is required."))

		delivery_qty = flt(delivery_qty)
		if delivery_qty < 0:
			frappe.throw(_("Quantity cannot be negative."))

		row = frappe.db.get_value(
			"Preparation Storage Details",
			{"name": row_name, "parent": pon_name, "parenttype": "Preparation Order Note"},
			[
				"name", "item", "item_name", "bin_location_name", "pallet",
				"batch_no", "delivery_qty", "expiry_date", "warehouse",
				"sub_customer", "uom", "qty_required", "stored_qty",
				"stored_in", "area_used", "height", "width", "length",
				"description", "required_date",
			],
			as_dict=True,
		)
		if not row:
			frappe.throw(_("Storage row {0} not found on order {1}.").format(row_name, pon_name))

		pon_doc = frappe.get_doc("Preparation Order Note", pon_name)

		existing = next(
			(s for s in pon_doc.get("scanned_items")
			 if s.get("bin_location_name") == row.bin_location_name
			 and s.get("batch_no") == row.batch_no
			 and s.get("pallet") == row.pallet),
			None,
		)

		if existing:
			existing.delivery_qty = delivery_qty
		else:
			pon_doc.append("scanned_items", {
				"item":              row.item,
				"item_name":         row.item_name,
				"bin_location_name": row.bin_location_name,
				"pallet":            row.pallet,
				"batch_no":          row.batch_no,
				"delivery_qty":      delivery_qty,
				"expiry_date":       row.expiry_date,
				"warehouse":         row.warehouse,
				"sub_customer":      row.sub_customer,
				"uom":               row.uom,
				"qty_required":      row.qty_required,
				"stored_qty":        row.stored_qty,
				"stored_in":         row.stored_in,
				"area_used":         row.area_used,
				"height":            row.height,
				"width":             row.width,
				"length":            row.length,
				"description":       row.description,
				"required_date":     row.required_date,
			})

		total_scanned = sum(flt(s.delivery_qty) for s in pon_doc.get("scanned_items"))
		pon_doc.scanned_qty = total_scanned
		pon_doc.flags.ignore_permissions = True
		pon_doc.save()

		return {
			"scanned_row":  row_name,
			"delivery_qty": delivery_qty,
			"total_scanned": total_scanned,
		}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: submit_scan failed PON {pon_name} row {row_name}")
		raise


# ─── 4. Finalize scan ─────────────────────────────────────────────────────────

@frappe.whitelist()
def finalize_scan(pon_name=None):
	"""Validate all storage rows are scanned then set allow_delivery = 1."""
	try:
		_assert_stock_role()

		pon_name = pon_name or frappe.form_dict.get('pon_name')
		if not pon_name:
			frappe.throw(_("pon_name is required."))

		pon_doc      = frappe.get_doc("Preparation Order Note", pon_name)
		storage_rows = pon_doc.get("storage_details")

		scanned_map = {}
		for s in pon_doc.get("scanned_items"):
			key = (s.get("bin_location_name") or "", s.get("batch_no") or "", s.get("pallet") or "")
			scanned_map[key] = s

		missing    = []
		mismatches = []

		for row in storage_rows:
			key = (row.bin_location_name or "", row.batch_no or "", row.pallet or "")
			if key not in scanned_map:
				missing.append(f"{row.bin_location_name} / {row.pallet or '-'} — {row.item_name}")
				continue
			scan = scanned_map[key]
			if flt(scan.delivery_qty) != flt(row.delivery_qty):
				mismatches.append(
					f"{row.bin_location_name} / {row.pallet or '-'}: "
					f"expected {row.delivery_qty}, scanned {scan.delivery_qty}"
				)

		if missing:
			frappe.throw(_("The following items have not been scanned:\n{0}").format("\n".join(missing)))
		if mismatches:
			frappe.throw(_("Quantity mismatches:\n{0}").format("\n".join(mismatches)))

		pon_doc.allow_delivery = "1"
		pon_doc.order_status   = "To make Delivery Note"
		pon_doc.flags.ignore_permissions = True
		pon_doc.save()

		return {
			"success": True,
			"message": f"All {len(storage_rows)} items scanned. Delivery Note creation is now enabled on the desk.",
		}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: finalize_scan failed for PON {pon_name}")
		raise


# ─── 5. Bin transfer ──────────────────────────────────────────────────────────

@frappe.whitelist()
def get_bin_contents(bin_name=None):
	"""Return what is stored in a bin (for transfer source preview)."""
	try:
		_assert_stock_role()
		bin_name = bin_name or frappe.form_dict.get('bin_name')
		if not bin_name:
			frappe.throw(_("bin_name is required."))
		if not frappe.db.exists("Bin Name", bin_name):
			frappe.throw(_("Bin {0} not found.").format(bin_name))

		status = frappe.db.get_value("Bin Name", bin_name, "status")
		rows   = frappe.db.sql(
			"""
			SELECT
				c.name,
				c.parent AS item_code,
				c.pallet,
				c.bin_location,
				c.stored_qty,
				c.batch_no,
				DATE_FORMAT(c.expiry, '%%d-%%m-%%Y') AS expiry,
				c.warehouse
			FROM `tabitem bin location` c
			WHERE c.bin_location = %s AND c.stored_qty > 0
			""",
			(bin_name,),
			as_dict=True,
		)
		for r in rows:
			r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code

		return {"bin_name": bin_name, "status": status, "contents": rows, "is_empty": len(rows) == 0}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: get_bin_contents failed for bin {bin_name}")
		raise


@frappe.whitelist()
def do_bin_transfer(source_bin=None, target_bin=None):
	"""Move stock from source_bin to target_bin via Transfer Bin doctype."""
	try:
		_assert_stock_role()
		source_bin = source_bin or frappe.form_dict.get('source_bin')
		target_bin = target_bin or frappe.form_dict.get('target_bin')

		if not source_bin or not target_bin:
			frappe.throw(_("Both source_bin and target_bin are required."))
		if source_bin == target_bin:
			frappe.throw(_("Source and target bin cannot be the same."))

		if frappe.db.get_value("Bin Name", source_bin, "status") == "Vacant":
			frappe.throw(_("Source bin {0} is vacant.").format(source_bin))
		if frappe.db.get_value("Bin Name", target_bin, "status") == "Occupied":
			frappe.throw(_("Target bin {0} is already occupied.").format(target_bin))

		source_rows = frappe.db.sql(
			"SELECT name FROM `tabitem bin location` WHERE bin_location = %s AND stored_qty > 0",
			(source_bin,),
		)
		if not source_rows:
			frappe.throw(_("Source bin {0} has no stock.").format(source_bin))
		if len(source_rows) > 1:
			frappe.throw(_("Bin {0} holds multiple stock records — transfer it on the desk.").format(source_bin))

		doc = frappe.new_doc("Transfer Bin")
		doc.source_bin = source_bin
		doc.source_barcode = source_bin
		doc.target_bin = target_bin
		doc.target_barcode = target_bin
		doc.flags.ignore_permissions = True
		doc.save()
		doc.submit()

		return {"success": True, "transfer": doc.name, "message": f"Moved stock from {source_bin} to {target_bin}."}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: do_bin_transfer failed {source_bin} -> {target_bin}")
		raise


# ─── 6. Receiving / put-away ──────────────────────────────────────────────────

@frappe.whitelist()
def get_open_receipts():
	"""Draft Material Receipts that still have storage rows without a bin."""
	try:
		_assert_stock_role()
		rows = frappe.db.sql(
			"""
			SELECT
				se.name,
				se.posting_date,
				se.customer_nm  AS customer,
				se.total_items  AS total_qty,
				(SELECT COUNT(*) FROM `tabStorage details` s WHERE s.parent = se.name) AS total_rows,
				(SELECT COUNT(*) FROM `tabStorage details` s
				 WHERE s.parent = se.name
				 AND (s.bin_location IS NULL OR s.bin_location = '')) AS pending_rows
			FROM `tabStock Entry` se
			WHERE se.stock_entry_type = 'Material Receipt'
			AND se.docstatus = 0
			HAVING total_rows > 0
			ORDER BY se.modified DESC
			LIMIT 50
			""",
			as_dict=True,
		)
		return rows
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Scan API: get_open_receipts failed")
		raise


@frappe.whitelist()
def get_receipt_rows(se_name=None):
	"""Return pre-split storage rows of a draft receipt."""
	try:
		_assert_stock_role()
		se_name = se_name or frappe.form_dict.get('se_name')
		if not se_name:
			frappe.throw(_("se_name is required."))

		se = frappe.db.get_value(
			"Stock Entry", se_name,
			["name", "stock_entry_type", "customer_nm", "posting_date", "docstatus"],
			as_dict=True,
		)
		if not se:
			frappe.throw(_("Stock Entry {0} not found.").format(se_name))
		if se.docstatus != 0:
			frappe.throw(_("This receipt is already submitted."))

		rows = frappe.db.sql(
			"""
			SELECT
				s.name,
				s.item_code,
				s.item_name,
				s.stored_qty,
				s.pallet,
				s.bin_location,
				s.batch_no,
				DATE_FORMAT(s.expiry, '%%Y-%%m-%%d') AS expiry,
				s.t_ware_house AS warehouse,
				s.uom
			FROM `tabStorage details` s
			WHERE s.parent = %s AND s.parenttype = 'Stock Entry'
			ORDER BY s.idx
			""",
			(se_name,),
			as_dict=True,
		)

		pending = sum(1 for r in rows if not r.bin_location)
		return {"stock_entry": se, "rows": rows, "total_rows": len(rows), "pending_rows": pending}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: get_receipt_rows failed for {se_name}")
		raise


@frappe.whitelist()
def assign_bin_to_row(se_name=None, row_name=None, bin_location=None):
	"""Assign a scanned empty bin to one pre-split storage row."""
	try:
		_assert_stock_role()
		se_name      = se_name      or frappe.form_dict.get('se_name')
		row_name     = row_name     or frappe.form_dict.get('row_name')
		bin_location = bin_location or frappe.form_dict.get('bin_location')

		if not se_name or not row_name or not bin_location:
			frappe.throw(_("se_name, row_name and bin_location are required."))
		if not frappe.db.exists("Bin Name", bin_location):
			frappe.throw(_("Bin {0} does not exist.").format(bin_location))

		assert_bin_not_held(bin_location, "Stock cannot be put away into a held bin.")
		bin_status   = frappe.db.get_value("Bin Name", bin_location, "status")
		stored_total = frappe.db.sql(
			"SELECT COALESCE(SUM(stored_qty),0) FROM `tabitem bin location` WHERE bin_location=%s AND stored_qty>0",
			(bin_location,),
		)[0][0]

		if flt(stored_total) > 0:
			frappe.throw(_("Bin {0} is not empty — it holds {1} units.").format(bin_location, flt(stored_total)))
		if bin_status == "Occupied":
			frappe.throw(_("Bin {0} is marked Occupied.").format(bin_location))

		se = frappe.get_doc("Stock Entry", se_name)
		if se.docstatus != 0:
			frappe.throw(_("This receipt is already submitted."))

		for r in se.get("storage_details"):
			if r.name != row_name and (r.bin_location or "") == bin_location:
				frappe.throw(_("Bin {0} is already assigned to another row on this receipt.").format(bin_location))

		target = next((r for r in se.get("storage_details") if r.name == row_name), None)
		if not target:
			frappe.throw(_("Storage row not found on this receipt."))

		target.bin_location = bin_location
		se.flags.ignore_permissions = True
		se.save()
		frappe.db.set_value("Bin Name", bin_location, "status", "Occupied")

		pending = sum(1 for r in se.get("storage_details") if not r.bin_location)
		return {
			"success": True, "row": row_name, "bin": bin_location,
			"item_code": target.item_code, "stored_qty": target.stored_qty, "pending_rows": pending,
		}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: assign_bin_to_row failed SE {se_name} row {row_name} bin {bin_location}")
		raise


@frappe.whitelist()
def clear_bin_from_row(se_name=None, row_name=None):
	"""Undo: remove bin from a storage row and free it back to Vacant."""
	try:
		_assert_stock_role()
		se_name  = se_name  or frappe.form_dict.get('se_name')
		row_name = row_name or frappe.form_dict.get('row_name')

		se = frappe.get_doc("Stock Entry", se_name)
		if se.docstatus != 0:
			frappe.throw(_("This receipt is already submitted."))

		target = next((r for r in se.get("storage_details") if r.name == row_name), None)
		if not target:
			frappe.throw(_("Row not found."))

		old_bin             = target.bin_location
		target.bin_location = None
		se.flags.ignore_permissions = True
		se.save()

		if old_bin:
			still_used = any((r.bin_location or "") == old_bin for r in se.get("storage_details"))
			has_stock  = frappe.db.exists("item bin location", {"bin_location": old_bin, "stored_qty": (">", 0)})
			if not still_used and not has_stock:
				frappe.db.set_value("Bin Name", old_bin, "status", "Vacant")

		return {"success": True, "freed_bin": old_bin}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: clear_bin_from_row failed SE {se_name} row {row_name}")
		raise


# ─── 7. Bin / pallet lookup ───────────────────────────────────────────────────

@frappe.whitelist()
def lookup_scan(scan_value=None):
	"""Scan a bin or pallet barcode and return full stock info."""
	try:
		_assert_stock_role()
		scan_value = scan_value or frappe.form_dict.get('scan_value')
		if not scan_value:
			frappe.throw(_("scan_value is required."))

		scan_value = scan_value.strip()
		query = """
			SELECT
				c.parent AS item_code, c.bin_location, c.pallet, c.warehouse,
				c.stored_qty, COALESCE(c.reserved_qty,0) AS reserved_qty,
				(c.stored_qty - COALESCE(c.reserved_qty,0)) AS available_qty,
				c.batch_no,
				DATE_FORMAT(c.expiry,'%%d-%%m-%%Y') AS expiry,
				DATE_FORMAT(c.manufacturing_date,'%%d-%%m-%%Y') AS manufacturing_date,
				c.sub_customer, c.area_use
			FROM `tabitem bin location` c
			WHERE c.{col} = %s AND c.stored_qty > 0
		"""

		rows       = frappe.db.sql(query.format(col="bin_location"), (scan_value,), as_dict=True)
		matched_as = "bin"

		if not rows:
			rows       = frappe.db.sql(query.format(col="pallet"), (scan_value,), as_dict=True)
			matched_as = "pallet"

		bin_status = None
		if frappe.db.exists("Bin Name", scan_value):
			bin_status = frappe.db.get_value("Bin Name", scan_value, "status")
			matched_as = matched_as if rows else "bin"

		if not rows:
			return {
				"found": False, "scan_value": scan_value,
				"matched_as": "bin" if bin_status else "unknown",
				"bin_status": bin_status,
				"message": _("Nothing stored under {0}.").format(scan_value)
				           + ((" Bin status: " + bin_status) if bin_status else ""),
			}

		for r in rows:
			r["item_name"] = frappe.db.get_value("Item", r.item_code, "item_name") or r.item_code
			r["customer"]  = frappe.db.get_value("Item", r.item_code, "customer_") or ""

		return {"found": True, "scan_value": scan_value, "matched_as": matched_as, "bin_status": bin_status, "records": rows}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: lookup_scan failed for value '{scan_value}'")
		raise


# ─── 8. is_bin_empty ──────────────────────────────────────────────────────────

@frappe.whitelist()
def is_bin_empty(bin_name=None):
	"""Check Bin Name status AND actual stored qty."""
	try:
		_assert_stock_role()
		bin_name = bin_name or frappe.form_dict.get('bin_name')
		if not bin_name:
			frappe.throw(_("bin_name is required."))

		if not frappe.db.exists("Bin Name", bin_name):
			return {"empty": False, "reason": "not_found", "message": _("Bin {0} does not exist.").format(bin_name)}

		status = frappe.db.get_value("Bin Name", bin_name, "status")
		stored = frappe.db.sql(
			"SELECT COALESCE(SUM(stored_qty),0) AS qty FROM `tabitem bin location` WHERE bin_location=%s AND stored_qty>0",
			(bin_name,), as_dict=True,
		)[0]

		if flt(stored.qty) > 0:
			return {"empty": False, "reason": "has_stock", "message": _("Bin {0} already holds {1} units.").format(bin_name, flt(stored.qty))}
		if status == "Occupied":
			return {"empty": False, "reason": "marked_occupied", "message": _("Bin {0} is marked Occupied.").format(bin_name)}

		return {"empty": True, "status": status, "message": _("Bin {0} is empty and available.").format(bin_name)}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: is_bin_empty failed for bin {bin_name}")
		raise


# ─── 9. Bin put-away validation ───────────────────────────────────────────────

@frappe.whitelist()
def check_bin_for_putaway(bin_name=None, item_code=None, batch_no=None, expiry=None):
	"""Check if a bin is suitable for the item being placed during receiving.

	Returns status: vacant | partial_match | partial_mismatch | not_found
	"""
	try:
		_assert_stock_role()
		bin_name  = bin_name  or frappe.form_dict.get('bin_name')
		item_code = (item_code or frappe.form_dict.get('item_code') or "").strip()
		batch_no  = (batch_no  or frappe.form_dict.get('batch_no')  or "").strip()
		expiry    = (expiry    or frappe.form_dict.get('expiry')    or "").strip()

		if not frappe.db.exists("Bin Name", bin_name):
			return {"status": "not_found", "message": _("Bin {0} does not exist.").format(bin_name)}

		held = get_hold_info(bin_name)
		if held:
			return {
				"status": "not_found",
				"message": _("Bin {0} is on hold ({1}). Stock cannot be put away into it.").format(
					bin_name, held.hold_reason or held.hold_ref or "-"
				),
			}

		existing = frappe.db.sql(
			"""
			SELECT
				parent AS item_code,
				COALESCE(batch_no,'') AS batch_no,
				COALESCE(DATE_FORMAT(expiry,'%%Y-%%m-%%d'),'') AS expiry,
				stored_qty
			FROM `tabitem bin location`
			WHERE bin_location = %s AND stored_qty > 0
			ORDER BY expiry LIMIT 5
			""",
			(bin_name,), as_dict=True,
		)

		if not existing:
			return {"status": "vacant", "message": _("Bin {0} is empty and ready.").format(bin_name)}

		total_stored = sum(flt(r.stored_qty) for r in existing)
		first        = existing[0]

		all_match = all(
			r.item_code == item_code
			and r.batch_no == batch_no
			and (not expiry or not r.expiry or r.expiry == expiry)
			for r in existing
		)

		if all_match:
			return {
				"status": "partial_match",
				"message": _(
					"Bin {0} already holds {1} of the same stock (item {2}, batch {3}). "
					"Stock will be consolidated."
				).format(bin_name, total_stored, item_code, batch_no or "-"),
				"existing_qty": total_stored,
			}

		return {
			"status": "partial_mismatch",
			"message": _(
				"Bin {0} already contains different stock: {1} batch {2} expiry {3}. "
				"Cannot place {4} here — mixing is not allowed."
			).format(bin_name, first.item_code, first.batch_no or "-", first.expiry or "-", item_code),
			"existing_item": first.item_code, "existing_batch": first.batch_no, "existing_expiry": first.expiry,
		}
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Scan API: check_bin_for_putaway failed bin {bin_name} item {item_code}")
		raise


# ─── 10. Site branding ────────────────────────────────────────────────────────

@frappe.whitelist(allow_guest=True)
def get_site_branding():
	"""Return site logo URL + app name for in-app branding. allow_guest so it works before login."""
	try:
		logo_path = None
		try:
			logo_path = frappe.db.get_single_value("Website Settings", "app_logo")
		except Exception:
			pass
		if not logo_path:
			try:
				logo_path = frappe.db.get_single_value("Navbar Settings", "app_logo")
			except Exception:
				pass

		site_title = None
		try:
			site_title = frappe.db.get_single_value("Website Settings", "app_name")
		except Exception:
			pass

		logo_url = None
		if logo_path:
			base     = frappe.utils.get_url()
			logo_url = logo_path if logo_path.startswith("http") else f"{base}{logo_path}"

		return {"logo_url": logo_url, "site_title": site_title or frappe.local.site}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Scan API: get_site_branding failed")
		return {"logo_url": None, "site_title": None}