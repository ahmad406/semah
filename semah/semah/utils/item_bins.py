import frappe
from frappe.utils import now

BIN_DOCTYPE = "item bin location"


class ItemBins:
	"""Row-level stand-in for frappe.get_doc("Item") when only the `bin` table changes.

	Item.save() rewrites every bin row, so one movement on an item with thousands of
	bins costs thousands of writes and holds the locks until the request ends.
	"""

	def __init__(self, item_code):
		self.item_code = item_code
		# Serialises movements on one item, including an item with no bin rows yet.
		if not frappe.db.get_value("Item", item_code, "name", for_update=True):
			frappe.throw(frappe._("Item {0} not found").format(item_code), frappe.DoesNotExistError)
		# FOR UPDATE also forces a current read; a plain SELECT would see the
		# transaction snapshot and lose concurrent quantity changes.
		self.bin = frappe.db.sql(
			"""
			SELECT * FROM `tabitem bin location`
			WHERE parent = %s AND parenttype = 'Item' AND parentfield = 'bin'
			ORDER BY idx
			FOR UPDATE
			""",
			(item_code,),
			as_dict=True,
		)
		self._snapshot()

	def _snapshot(self):
		self._saved = {row.name: dict(row) for row in self.bin if row.get("name")}

	def append(self, fieldname, value=None):
		row = frappe._dict(value or {})
		getattr(self, fieldname).append(row)
		return row

	def save(self):
		changed = False
		next_idx = max((row.idx or 0 for row in self.bin if row.get("name")), default=0) + 1

		for row in self.bin:
			if not row.get("name"):
				doc = frappe.get_doc(
					{
						**row,
						"doctype": BIN_DOCTYPE,
						"parent": self.item_code,
						"parenttype": "Item",
						"parentfield": "bin",
						"idx": next_idx,
					}
				)
				doc.db_insert()
				row.update(name=doc.name, idx=next_idx)
				next_idx += 1
				changed = True
				continue

			saved = self._saved[row.name]
			updates = {key: value for key, value in row.items() if saved.get(key) != value}
			if updates:
				frappe.db.set_value(BIN_DOCTYPE, row.name, updates)
				changed = True

		if changed:
			# Keeps the timestamp check working for anyone with this Item open in a form,
			# whose stale copy of the bin table would otherwise overwrite these rows.
			frappe.db.set_value(
				"Item",
				self.item_code,
				{"modified": now(), "modified_by": frappe.session.user},
				update_modified=False,
			)
			frappe.clear_document_cache("Item", self.item_code)

		self._snapshot()


def load_item_bins(item_codes):
	"""Lock in sorted order so two documents sharing items cannot deadlock each other."""
	return {item_code: ItemBins(item_code) for item_code in sorted(set(item_codes))}


def save_item_bins(bins_by_item):
	for item_bins in bins_by_item.values():
		item_bins.save()
