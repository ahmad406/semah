# Copyright (c) 2026, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class StockHoldandReleaseNote(Document):
	def validate(self):
		if not self.get("bins"):
			frappe.throw(_("Add at least one bin. Use <b>Fetch Bins</b> to load them."))
		if self.action == "Hold" and not (self.reason or "").strip():
			frappe.throw(_("Reason is required to hold a bin."))

		self.validate_duplicate_bins()
		self.refresh_rows()
		self.validate_hold_state()

	def validate_duplicate_bins(self):
		seen = set()
		for row in self.bins:
			if row.bin in seen:
				frappe.throw(_("Row {0}: bin <b>{1}</b> is repeated.").format(row.idx, row.bin))
			seen.add(row.bin)

	def refresh_rows(self):
		"""Recompute quantities and hold flag from the database so the table can't be tampered with."""
		contents = get_bin_contents([r.bin for r in self.bins])
		for row in self.bins:
			info = contents.get(row.bin) or {}
			row.warehouse = info.get("warehouse") or ""
			row.items_in_bin = info.get("items_in_bin") or _("Empty bin")
			row.stored_qty = flt(info.get("stored_qty"))
			row.reserved_qty = flt(info.get("reserved_qty"))
			row.free_qty = row.stored_qty - row.reserved_qty
			row.currently_on_hold = 1 if info.get("on_hold") else 0

	def validate_hold_state(self):
		errors = []
		for row in self.bins:
			if self.action == "Hold" and flt(row.reserved_qty) > 0:
				pons = get_reserving_pons(row.bin)
				errors.append(
					_("Row {0}: bin <b>{1}</b> has {2} reserved on Preparation Order Note {3}. "
					  "Complete or cancel it before holding the bin.").format(
						row.idx, row.bin, row.reserved_qty, ", ".join(pons) if pons else "-"
					)
				)
				continue
			if self.action == "Hold" and row.currently_on_hold:
				errors.append(_("Row {0}: bin <b>{1}</b> is already on hold.").format(row.idx, row.bin))
			if self.action == "Release" and not row.currently_on_hold:
				errors.append(_("Row {0}: bin <b>{1}</b> is not on hold.").format(row.idx, row.bin))
		if errors:
			frappe.throw("<br>".join(errors))

	def on_submit(self):
		now = now_datetime()
		for row in self.bins:
			bn = self._lock_bin(row.bin)
			if self.action == "Hold":
				if bn.on_hold:
					frappe.throw(_("Bin <b>{0}</b> is already on hold ({1}).").format(row.bin, bn.hold_ref or "-"))
				frappe.db.set_value("Bin Name", row.bin, {
					"on_hold": 1,
					"hold_reason": self.reason,
					"held_by": frappe.session.user,
					"held_on": now,
					"hold_ref": self.name,
				})
			else:
				if not bn.on_hold:
					frappe.throw(_("Bin <b>{0}</b> is not on hold.").format(row.bin))
				# keep what was released so a cancel of this note can restore it
				row.db_set("prior_hold_reason", bn.hold_reason)
				row.db_set("prior_hold_ref", bn.hold_ref)
				self._clear_hold(row.bin)

	def on_cancel(self):
		for row in self.bins:
			bn = self._lock_bin(row.bin)
			if self.action == "Hold":
				if not bn.on_hold or bn.hold_ref != self.name:
					frappe.throw(
						_("Bin <b>{0}</b> is no longer held by this note (current hold note: {1}). "
						  "Cancel the later note first.").format(row.bin, bn.hold_ref or _("none"))
					)
				self._clear_hold(row.bin)
			else:
				if bn.on_hold:
					frappe.throw(
						_("Bin <b>{0}</b> is on hold again ({1}). Cancel that note first.").format(row.bin, bn.hold_ref or "-")
					)
				prior = row.prior_hold_ref
				held_by, held_on = frappe.session.user, now_datetime()
				if prior and frappe.db.exists("Stock Hold and Release Note", prior):
					held_by, held_on = frappe.db.get_value("Stock Hold and Release Note", prior, ["owner", "modified"])
				frappe.db.set_value("Bin Name", row.bin, {
					"on_hold": 1,
					"hold_reason": row.prior_hold_reason,
					"held_by": held_by,
					"held_on": held_on,
					"hold_ref": prior,
				})

	@staticmethod
	def _lock_bin(bin_name):
		return frappe.db.get_value(
			"Bin Name", bin_name, ["on_hold", "hold_reason", "hold_ref"], as_dict=True, for_update=True
		)

	@staticmethod
	def _clear_hold(bin_name):
		frappe.db.set_value("Bin Name", bin_name, {
			"on_hold": 0, "hold_reason": None, "held_by": None, "held_on": None, "hold_ref": None,
		})

	@frappe.whitelist()
	def fetch_bins(self):
		"""Return the bins matching the filters, ready to fill the table."""
		if self.docstatus != 0:
			frappe.throw(_("Bins can only be fetched on a draft note."))
		if not self.action:
			frappe.throw(_("Select the Action (Hold or Release) first."))

		bins = find_bins(
			receipt_no=self.receipt_no, bin_name=self.bin, item=self.item,
			warehouse=self.warehouse, customer=self.customer, batch_no=self.batch_no,
		)
		contents = get_bin_contents(bins)

		rows = []
		skipped = []
		for b in bins:
			info = contents.get(b) or {}
			if self.action == "Hold" and info.get("on_hold"):
				continue
			if self.action == "Hold" and flt(info.get("reserved_qty")) > 0:
				skipped.append(b)
				continue
			if self.action == "Release" and not info.get("on_hold"):
				continue
			rows.append({
				"bin": b,
				"warehouse": info.get("warehouse") or "",
				"items_in_bin": info.get("items_in_bin") or _("Empty bin"),
				"stored_qty": flt(info.get("stored_qty")),
				"reserved_qty": flt(info.get("reserved_qty")),
				"free_qty": flt(info.get("stored_qty")) - flt(info.get("reserved_qty")),
				"currently_on_hold": 1 if info.get("on_hold") else 0,
			})
		return {"rows": rows, "skipped": skipped}


def get_reserving_pons(bin_name):
	"""Open Preparation Order Notes that reserve stock from this bin."""
	return [r[0] for r in frappe.db.sql(
		"""
		SELECT DISTINCT p.name FROM `tabPreparation Order Note` p
		INNER JOIN `tabPreparation Storage Details` c ON c.parent = p.name
		WHERE c.bin_location_name = %s AND p.docstatus = 1 AND p.order_status = 'To make Delivery Note'
		""",
		(bin_name,),
	)]


def find_bins(receipt_no=None, bin_name=None, item=None, warehouse=None, customer=None, batch_no=None):
	"""Bins that hold stock matching the filters. At least one filter is required."""
	if not any([receipt_no, bin_name, item, warehouse, customer, batch_no]):
		frappe.throw(_("Enter at least one filter: Receipt No, Bin, Item, Warehouse, Customer or Batch."))

	conds = ["c.stored_qty > 0", "IFNULL(c.bin_location, '') != ''"]
	params = {}

	if receipt_no:
		se = frappe.db.get_value("Stock Entry", receipt_no, ["docstatus", "stock_entry_type"], as_dict=True)
		if not se:
			frappe.throw(_("Stock Entry {0} not found.").format(receipt_no))
		if se.docstatus != 1 or se.stock_entry_type != "Material Receipt":
			frappe.throw(_("{0} must be a submitted Material Receipt.").format(receipt_no))
		conds.append("""EXISTS (
			SELECT 1 FROM `tabStorage details` sd
			WHERE sd.parent = %(receipt_no)s AND sd.parenttype = 'Stock Entry'
			AND sd.item_code = c.parent
			AND sd.bin_location = c.bin_location
			AND IFNULL(sd.pallet, '') = IFNULL(c.pallet, '')
			AND IFNULL(NULLIF(sd.batch_no, ''), IFNULL(sd.batch, '')) = IFNULL(c.batch_no, '')
		)""")
		params["receipt_no"] = receipt_no
	if bin_name:
		conds.append("c.bin_location = %(bin_name)s")
		params["bin_name"] = bin_name
	if item:
		conds.append("c.parent = %(item)s")
		params["item"] = item
	if batch_no:
		conds.append("c.batch_no = %(batch_no)s")
		params["batch_no"] = batch_no
	if customer:
		conds.append("p.customer_ = %(customer)s")
		params["customer"] = customer
	if warehouse:
		lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"]) or (None, None)
		if lft is None:
			frappe.throw(_("Warehouse {0} not found.").format(warehouse))
		conds.append("""c.warehouse IN (
			SELECT name FROM `tabWarehouse` WHERE lft >= %(lft)s AND rgt <= %(rgt)s
		)""")
		params.update({"lft": lft, "rgt": rgt})

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT c.bin_location
		FROM `tabitem bin location` c
		INNER JOIN `tabItem` p ON p.name = c.parent
		WHERE {0}
		ORDER BY c.bin_location
		""".format(" AND ".join(conds)),
		params,
	)
	return [r[0] for r in rows]


def get_bin_contents(bins):
	"""Full contents of each bin (all items, batches, pallets) plus its hold flag."""
	bins = [b for b in bins if b]
	if not bins:
		return {}

	out = {}
	for bn in frappe.get_all(
		"Bin Name", filters={"name": ["in", bins]}, fields=["name", "warehouse", "on_hold"]
	):
		out[bn.name] = {
			"warehouse": bn.warehouse, "on_hold": bn.on_hold,
			"stored_qty": 0, "reserved_qty": 0, "lines": [], "whs": set(),
		}

	stock = frappe.db.sql(
		"""
		SELECT c.bin_location, c.parent AS item_code, c.batch_no, c.pallet, c.warehouse,
			c.stored_qty, COALESCE(c.reserved_qty, 0) AS reserved_qty
		FROM `tabitem bin location` c
		WHERE c.stored_qty > 0 AND c.bin_location IN %(bins)s
		ORDER BY c.bin_location, c.parent
		""",
		{"bins": bins},
		as_dict=True,
	)
	for s in stock:
		d = out.get(s.bin_location)
		if not d:
			continue
		d["stored_qty"] += flt(s.stored_qty)
		d["reserved_qty"] += flt(s.reserved_qty)
		if s.warehouse:
			d["whs"].add(s.warehouse)
		parts = [s.item_code]
		if s.batch_no:
			parts.append("batch " + s.batch_no)
		if s.pallet:
			parts.append("pallet " + s.pallet)
		parts.append("qty " + str(flt(s.stored_qty)))
		d["lines"].append(" | ".join(parts))

	for d in out.values():
		if d["whs"]:
			d["warehouse"] = ", ".join(sorted(d["whs"]))
		d["items_in_bin"] = "\n".join(d["lines"])
	return out
