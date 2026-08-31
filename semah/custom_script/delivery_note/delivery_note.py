from collections import defaultdict
import datetime
import frappe
from frappe.utils import flt
from erpnext.stock.doctype.delivery_note.delivery_note import DeliveryNote
from erpnext.stock.doctype.delivery_note.delivery_note import *


def _calculate_area_use(length, width, height, stored_qty):
	if not height:
		return length * width * stored_qty
	return length * width * height * stored_qty


def convert_to_string(date):
	if isinstance(date, datetime.date):
		return date.strftime('%Y-%m-%d')
	return date


class CustomDeliveryNote(DeliveryNote):

	def update_preparation_order(self, is_canceled=None):
		if not self.prepration:
			frappe.throw("Preparation Order is not linked.")

		order = frappe.get_doc('Preparation Order Note', self.prepration)

		if is_canceled:
			order.update_reserved_qty(is_reduced=False, is_cancel=True)
		else:
			order.update_reserved_qty(is_reduced=True)

	@frappe.whitelist()
	def before_submit(self):
		self.update_bin_status()
		self.update_preparation_order()

		# Group storage rows by item_code so each item is fetched and saved once
		rows_by_item = defaultdict(list)
		for storage in self.get('storage_details'):
			rows_by_item[storage.item_code].append(storage)

		for item_code, rows in rows_by_item.items():
			item = frappe.get_doc("Item", item_code)

			for storage in rows:
				matched = False

				for bin_entry in item.bin:
					if bin_entry.stored_qty <= 0:
						continue

					conditions_met = (
						(storage.batch_no == bin_entry.batch_no if storage.batch_no else True) and
						(storage.bin_location_name == bin_entry.bin_location) and
						(storage.warehouse == bin_entry.warehouse) and
						(convert_to_string(storage.expiry_date) == convert_to_string(bin_entry.expiry) if storage.expiry_date else True) and
						(storage.pallet == bin_entry.pallet if storage.pallet else True)
					)

					if conditions_met:
						if bin_entry.stored_qty < storage.delivery_qty:
							frappe.throw(
								f"Cannot deliver {storage.delivery_qty} from bin "
								f"'{bin_entry.bin_location}' for item {storage.item_code} "
								f"— only {bin_entry.stored_qty} available in stock."
							)
						bin_entry.stored_qty -= storage.delivery_qty
						bin_entry.area_use = _calculate_area_use(
							storage.length, storage.width,
							storage.height, bin_entry.stored_qty
						)
						matched = True
						break

				if not matched:
					frappe.throw(
						f"No matching bin found for item {storage.item_code} "
						f"in warehouse '{storage.warehouse}', "
						f"bin '{storage.bin_location_name}', "
						f"pallet '{storage.pallet}', "
						f"batch '{storage.batch_no}'."
					)

			# All rows for this item mutated in memory — save once
			item.save()
		self.update_pon_status()

	def before_cancel(self):
		self.update_bin_status(canceled=True)

		rows_by_item = defaultdict(list)
		for storage in self.get('storage_details'):
			rows_by_item[storage.item_code].append(storage)

		for item_code, rows in rows_by_item.items():
			item = frappe.get_doc("Item", item_code)

			for storage in rows:
				matched = False

				for bin_entry in item.bin:
					conditions_met = (
						(storage.batch_no == bin_entry.batch_no if storage.batch_no else True) and
						(storage.bin_location_name == bin_entry.bin_location) and
						(storage.warehouse == bin_entry.warehouse) and
						(convert_to_string(storage.expiry_date) == convert_to_string(bin_entry.expiry) if storage.expiry_date else True) and
						(storage.pallet == bin_entry.pallet if storage.pallet else True)
					)

					if conditions_met:
						bin_entry.stored_qty += storage.delivery_qty
						bin_entry.area_use = _calculate_area_use(
							storage.length, storage.width,
							storage.height, bin_entry.stored_qty
						)
						matched = True
						break

				if not matched:
					frappe.throw(
						f"No matching bin found to revert for item {storage.item_code} "
						f"in warehouse '{storage.warehouse}', "
						f"bin '{storage.bin_location_name}', "
						f"pallet '{storage.pallet}', "
						f"batch '{storage.batch_no}'."
					)

			item.save()

		self.update_preparation_order(is_canceled=True)

	def update_bin_status(self, canceled=False):
		for row in self.get("storage_details"):
			bin_name = row.bin_location_name
			item_code = row.item_code
			pallet = row.pallet

			if not bin_name:
				frappe.throw(f"Bin location missing in row {row.idx or '[unknown]'}")

			if not pallet:
				frappe.throw(f"Pallet missing in row {row.idx or '[unknown]'}")

			existing_qty = frappe.db.sql("""
				SELECT SUM(stored_qty)
				FROM `tabitem bin location`
				WHERE bin_location = %s AND parent = %s AND pallet = %s
			""", (bin_name, item_code, pallet))[0][0] or 0

			current_qty = flt(row.delivery_qty) * (-1 if not canceled else 1)
			total_qty = flt(existing_qty + current_qty)

			try:
				pallet_doc = frappe.get_doc("Pallet", pallet)
				capacity = flt(pallet_doc.capacity)
			except frappe.DoesNotExistError:
				frappe.throw(f"Pallet '{pallet}' not found for bin '{bin_name}'")

			if total_qty <= 0:
				status = "Vacant"
			elif total_qty < capacity:
				status = "Partially Occupied"
			else:
				status = "Occupied"

			frappe.msgprint(f"Bin {bin_name} updated to {status}")
			frappe.db.set_value("Bin Name", bin_name, "status", status)



	def update_pon_status(self):
		frappe.db.set_value('Preparation Order Note', self.prepration, 'order_status', 'Completed')
		frappe.db.set_value('Delivery Request', self.delivery_request, 'doc_status', 'Completed')


@frappe.whitelist()
def get_item(customer):
	data = frappe.db.sql("""
		SELECT name, customer, name as name_1, customer as customer_1
		FROM `tabPreparation Order Note`
		WHERE customer = %s AND docstatus = 1
		ORDER BY creation DESC
	""", (customer,), as_dict=True)
	return data


@frappe.whitelist()
def background_recreate_d():
	frappe.enqueue(rebuild_bins_from_transactions, timeout=4800, queue='long',
		job_name='rebuild_bins_from_transactions', now=False)


def rebuild_bins_from_transactions():
	frappe.msgprint("🔁 Starting bin rebuild from submitted transactions...")

	other_entries = frappe.get_all(
		"Stock Entry",
		filters=[["docstatus", "=", 1], ["stock_entry_type", "!=", "Material Receipt"]]
	)
	for entry in other_entries:
		try:
			doc = frappe.get_doc("Stock Entry", entry.name)
			if hasattr(doc, "before_submit"):
				doc.before_submit()
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"❌ Error in Stock Entry (Other): {entry.name}")


@frappe.whitelist()
def recreating_all():
	sql = """SELECT name FROM `tabDelivery Note` WHERE docstatus = 1 ORDER BY posting_date"""
	for d in frappe.db.sql(sql, as_dict=1):
		delev = frappe.get_doc("Delivery Note", d.name)
		recreating(delev)


def recreating(delev):
	self = delev
	for s in self.get('storage_details'):
		items = frappe.get_doc("Item", s.item_code)
		to_update = False
		for i in items.bin:
			if s.batch_no:
				if s.expiry_date:
					if (i.batch_no == s.batch_no and
						i.bin_location == s.bin_location_name and
						s.warehouse == i.warehouse and
						convert_to_string(s.expiry_date) == convert_to_string(i.expiry)):
						i.stored_qty = i.stored_qty - s.delivery_qty
						i.area_use = _calculate_area_use(s.length, s.width, s.height, i.stored_qty)
						to_update = True
						break
				else:
					if (i.batch_no == s.batch_no and
						i.bin_location == s.bin_location_name and
						s.warehouse == i.warehouse):
						i.stored_qty = i.stored_qty - s.delivery_qty
						i.area_use = _calculate_area_use(s.length, s.width, s.height, i.stored_qty)
						to_update = True
						break
			else:
				if (i.bin_location == s.bin_location_name and
					s.warehouse == i.warehouse):
					i.stored_qty = i.stored_qty - s.delivery_qty
					i.area_use = _calculate_area_use(s.length, s.width, s.height, i.stored_qty)
					to_update = True
					break

		if to_update:
			frappe.errprint(self.name)
			items.save()
		else:
			frappe.throw("Nothing to update in item {0} {1}".format(s.item_code, s.parent))
