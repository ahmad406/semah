# Copyright (c) 2022, Dconnex and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document

from collections import defaultdict
from frappe.utils import flt
from semah.custom_script.delivery_note.delivery_note import convert_to_string



class PreparationOrderNote(Document):
	@frappe.whitelist()
	def update_reserved_qty(self, is_reduced=None, is_cancel=False):
		"""
		Update reserved quantity for items in storage_details.
		- is_reduced=True  : release reservation (Delivery Note submit)
		- is_reduced=False : add reservation (Preparation Order or Delivery Cancel)
		- is_cancel=True   : cancel flow; skip availability validation
		"""

		for storage in self.get('storage_details'):
			reserved = False
			# Always fetch item by item_code
			item = frappe.get_doc("Item", storage.item)

			# Ensure bin + pallet exist
			if not storage.bin_location_name or not storage.pallet:
				frappe.throw(
					f"Reservation requires both bin location and pallet for item {storage.item} (row {storage.idx})"
				)
			
			for bin_entry in item.bin:
				if storage.bin_location_name == bin_entry.bin_location and storage.pallet == bin_entry.pallet:
					if is_reduced:

						if bin_entry.reserved_qty < storage.delivery_qty:
							frappe.throw(
								f"Cannot release {storage.delivery_qty} reserved qty from bin '{bin_entry.bin_location}' "
								f"for item {storage.item}, pallet '{bin_entry.pallet}' — only {bin_entry.reserved_qty} reserved."
							)
						bin_entry.reserved_qty -= storage.delivery_qty
					else:
						if is_cancel:
							
							bin_entry.reserved_qty += storage.delivery_qty
						else:
							available_for_reserve = bin_entry.stored_qty - bin_entry.reserved_qty
							if available_for_reserve < storage.delivery_qty:
								frappe.throw(
									f"Cannot reserve {storage.delivery_qty} from bin '{bin_entry.bin_location}' "
									f"for item {storage.item}, pallet '{bin_entry.pallet}' — only {available_for_reserve} free to reserve."
								)
							bin_entry.reserved_qty += storage.delivery_qty

					reserved = True
					break 

			if not reserved and not is_cancel:
				frappe.throw(
					f"No matching bin with available stock to reserve for item {storage.item} "
					f"in warehouse '{storage.warehouse}' at bin '{storage.bin_location_name}' with pallet '{storage.pallet}'."
				)

			item.save()



	@frappe.whitelist()
	def update_storage_details(self):
		all_rows = []

		for itm in self.item_grid:
			item_code = itm.item_code
			qty_required = itm.qty_required

			if not item_code or qty_required is None:
				continue

			if qty_required <= 0:
				frappe.throw(f"Delivery qty can't be {qty_required} for item {item_code}")

			has_batch_no = frappe.db.get_value("Item", item_code, "has_batch_no")

			if has_batch_no:
				stock_rows = frappe.db.sql("""
					SELECT * FROM `tabitem bin location`
					WHERE parent = %s AND stored_qty - reserved_qty > 0 AND (expiry IS NULL OR expiry >= NOW())
					ORDER BY expiry ASC, stored_qty ASC
				""", (item_code,), as_dict=True)
			else:
				stock_rows = frappe.db.sql("""
					SELECT * FROM `tabitem bin location`
					WHERE parent = %s AND stored_qty - reserved_qty > 0
					ORDER BY stored_qty ASC
				""", (item_code,), as_dict=True)

			for stock in stock_rows:
				if qty_required <= 0:
					break

				available_qty = stock.stored_qty - stock.reserved_qty
				if available_qty <= 0:
					continue

				delivery_qty = min(qty_required, available_qty)
				qty_required -= delivery_qty

				# ✅ Optionally, reserve the quantity immediately
				frappe.db.set_value("Item Bin Location", stock.name, "reserved_qty",
					(stock.reserved_qty or 0) + delivery_qty)

				all_rows.append({
					"batch_no": stock.get("batch_no"),
					"item": item_code,
					"item_name": itm.item_name,
					"uom": itm.uom,
					"description": itm.item_description,
					"required_date": itm.required_date,
					"qty_required": itm.qty_required,
					"warehouse": stock.warehouse,
					"expiry_date": stock.expiry,
					"bin_location_name": stock.bin_location,
					"pallet": stock.pallet,
					"stored_qty": stock.stored_qty,
					"area_used": stock.area_use,
					"stored_in": stock.stored_in,
					"sub_customer": stock.sub_customer,
					"height": stock.height or None,
					"width": stock.width,
					"length": stock.length,
					"manufacture_date": stock.manufacturing_date,
					"delivery_qty": delivery_qty
				})

			if qty_required > 0:
				frappe.throw(f"Insufficient stock for item {item_code}")

		# Sort rows by bin location for better readability
		all_rows.sort(key=lambda x: x.get("bin_location_name") or "")

		# Clear old storage_details and append new allocation
		self.storage_details = []
		for row in all_rows:
			self.append("storage_details", row)

		self.calculate_total_qty()
		
		

	def on_submit(self):
		if self.delivery_request:
			dr = frappe.get_doc("Delivery Request", self.delivery_request)
			dr.db_set("doc_status", "To Make Delivery Note")

		self.update_reserved_qty()
		# if frappe.session.user!='Administrator':
		# 	self.validate_scanned()
	# def on_update_after_submit(self):
	# 	self.validate_scanned()



	def on_cancel(self):
		self.db_set("order_status", "Cancelled")

		self.update_reserved_qty(is_reduced=True)

	def validate(self):
		for i in self.item_grid:
			for s in self.storage_details:
				if i.item_code==s.item:
					s.uom=i.uom
					s.required_date	=i.required_date
					s.item_name	=i.item_name
					s.description	=i.item_description
		self.validate_duplicate_bin_locations()
		self.validate_required_item()
		self.calculate_scanned()
		self.calculate_total_qty()

	def calculate_total_qty(self):
		total_stored_qty = 0
		warehouse=None

		for d in self.storage_details:
			total_stored_qty += flt(d.delivery_qty or 0)
			if not warehouse:
				warehouse=d.warehouse

		self.total_delivery_quantity = total_stored_qty
		self.warehouse=warehouse
		



	def validate_scanned(self):
		scanned_map = defaultdict(float)
		for d in self.scanned_items:
			key = (d.item, d.pallet)
			scanned_map[key] += flt(d.delivery_qty)

		storage_map = defaultdict(float)
		for d in self.storage_details:
			key = (d.item, d.pallet)
			storage_map[key] += flt(d.delivery_qty)

		allow_delivery = 1

		for key, storage_qty in storage_map.items():
			scanned_qty = scanned_map.get(key)
			if scanned_qty is None:
				allow_delivery = 0
				frappe.throw(f"Item {key[0]} Pallet {key[1]} exists in Storage but not in Scanned Items.")
			elif flt(scanned_qty) != flt(storage_qty):
				allow_delivery = 0
				frappe.throw(
					f"Mismatch in Delivery Qty for Item {key[0]}, Pallet {key[1]}: "
					f"Scanned = {scanned_qty}, Storage = {storage_qty}"
				)

		for key in scanned_map:
			if key not in storage_map:
				allow_delivery = 0
				frappe.throw(f"Item {key[0]} Pallet {key[1]} exists in Scanned but not in Storage.")

		self.allow_delivery = allow_delivery   



	def validate_required_item(self):
		item_list = {d.item_code for d in self.item_grid}

		for row in self.storage_details:
			if row.item not in item_list:
				frappe.throw(
					_("Item <b>{0}</b> in Storage Details is not listed in Item Grid.").format(row.item),
					title=_("Validation Error")
				)


	
	def validate_duplicate_bin_locations(self):
		"""Validate that there are no duplicate bin_location_name values in the storage_details table."""
		if not self.bulk_stock_entry:
			bin_set = set()
			for row in self.storage_details:
				bin_name = (row.bin_location_name or "").strip().lower()

				if bin_name in bin_set:
					frappe.throw(
						_("Duplicate Bin Location found: {0}").format(row.bin_location_name),
						title=_("Validation Error")
					)
				if bin_name:
					bin_set.add(bin_name)
	@frappe.whitelist()
	def fetch_item_details(self, row,value_type):
		for d in self.storage_details:
			if str(d.idx) == str(row.get("idx")):
				if value_type == "Batch":
					cond = "AND c.batch_no = %s"
					param = d.batch_no
				else:
					cond = "AND c.bin_location = %s"
					param = d.bin_location_name

				data = frappe.db.sql(f"""
					SELECT
						p.stock_uom, p.item_name, p.description,
						p.name AS item_code, c.batch_no AS batch, c.warehouse,
						c.bin_location, c.expiry, c.stored_in, c.length, c.width, c.height,
						c.area_use, c.stored_qty, c.manufacturing_date, c.pallet
					FROM `tabitem bin location` c
					INNER JOIN `tabItem` p ON c.parent = p.name
					WHERE c.stored_qty > 0 {cond}
					LIMIT 1
				""", (param,), as_dict=1)


				if data:
					item = data[0]
					d.batch_no = item.batch
					d.item = item.item_code
					d.item_name = item.item_name
					d.uom = item.stock_uom
					d.description = item.description
					d.warehouse = item.warehouse
					d.expiry_date = item.expiry
					d.bin_location_name = item.bin_location
					d.pallet = item.pallet
					d.stored_qty = item.stored_qty
					d.area_used = item.area_use
					d.stored_in = item.stored_in
					d.height = item.height
					d.width = item.width
					d.length = item.length
					d.manufacture_date = item.manufacturing_date
					d.delivery_qty=item.stored_qty
					req_item=get_required_qty(self,item.item_code)
					d.qty_required = req_item.get("qty_required") if req_item else 0

					self.calculate_total_qty()
					return True



	@frappe.whitelist()
	def add_item_in_storage(self,insert=None):
		self.source_bin = self.barcode
		Type = ""
		self.validate_bin_pallet()

		if frappe.db.exists("Bin Name", self.source_bin):
			Type = "Bin"
		elif frappe.db.exists("Pallet", self.source_bin):
			Type = "Pallet"
		else:
			frappe.throw("Bin or Pallet not found.")

		def get_bin_details(bin_name, field_prefix):
			if field_prefix == "Bin":
				data = frappe.db.sql("""
					SELECT
						p.stock_uom, p.item_name,p.description,
						p.name AS item_code,c.batch_no AS batch, c.warehouse,
						c.bin_location, c.expiry, c.stored_in, c.length, c.width, c.height,
						c.area_use, c.stored_qty as stored_qty, c.manufacturing_date, c.pallet
					FROM `tabitem bin location` c
					INNER JOIN `tabItem` p ON c.parent = p.name
					
					WHERE c.stored_qty > 0 AND c.bin_location = %s
					LIMIT 2
				""", (bin_name,), as_dict=1)


			elif field_prefix == "Pallet":
				data = frappe.db.sql("""
					SELECT
						p.stock_uom, p.item_name,p.description,
						p.name AS item_code,c.batch_no AS batch, c.warehouse,
						c.bin_location, c.expiry, c.stored_in, c.length, c.width, c.height,
						c.area_use,  c.stored_qty as stored_qty, c.manufacturing_date, c.pallet
					FROM `tabitem bin location` c
					INNER JOIN `tabItem` p ON c.parent = p.name
					
					WHERE c.stored_qty > 0  AND c.pallet = %s
					LIMIT 2
				""", (bin_name,), as_dict=1)

			else:
				frappe.throw("Invalid field prefix for Bin or Pallet.")

			if not data:
				frappe.throw("No records found in the Bin or Pallet.")

			if len(data) > 1:
				frappe.throw(f"Multiple records found for {field_prefix} {bin_name}")

			return data[0]

		if self.source_bin:
			data = get_bin_details(self.source_bin, Type)
		
			if insert:
				if not self.qty:
					frappe.throw("Qty Required!")
				if self.qty > self.actual_qty:
					frappe.throw("Required Quantity cannot be greater than actual quantity.")
					return 

				# item = frappe.get_doc('Item', data['item_code'])

				row = self.append("scanned_items", {})
				row.item = data.get("item_code")
				row.item_name = data.get("item_name")
				row.uom = data.get("stock_uom")
				row.bin_location_name = data.get("bin_location")
				row.pallet = data.get("pallet")
				row.stored_qty = data.get("stored_qty")
				row.delivery_qty =self.qty
				if row.delivery_qty > row.stored_qty:
					frappe.throw("Deliver QTY cannot be more than  stored qty")
				row.expiry_date = data.get("expiry")
				row.manufacture_date = data.get("manufacturing_date")
				row.width = data.get("width")
				row.length = data.get("length")
				row.warehouse = data.get("warehouse")

				row.batch_no = data.get("batch")

				req_item = get_required_qty(self, data.get("item_code"))
				row.description = data.get("description")
				row.qty_required = req_item.qty_required if req_item else 0
				self.qty=0
				self.barcode=None
			else:
				# self.qty=data.get("stored_qty")
				self.qty=0

				self.actual_qty=data.get("stored_qty")

			self.calculate_scanned()
			return data
		
		else:
			frappe.msgprint("Scan properly.")
			return "No Show"
		
	def calculate_scanned(self):
		total=0
		for d in self.scanned_items:
			total+=d.delivery_qty
		self.scanned_qty=total
		
	def validate_bin_pallet(self):
		pallet_list = []
		bin_list = []

		for d in self.storage_details:
			pallet_list.append(d.pallet)
			bin_list.append(d.bin_location_name)

		if (self.barcode not in pallet_list) and (self.barcode not in bin_list):
			frappe.throw("Scanned barcode does not match any allocated pallet or bin for this Preparation Order Note.")


def get_required_qty(self, item):
	for d in self.item_grid:
		if d.item_code == item:
			return d
	frappe.throw("item is not in the required items list!")



@frappe.whitelist()
def get_delivery_request(customer):
	data=frappe.db.sql("""select dr.name,dr.customer  from `tabDelivery Request` as dr 
	 where dr.customer="{0}"  and dr.docstatus=1 and dr.doc_status="To make Preparation Order" order by dr.creation  desc """.format(customer),as_dict=True)
	return data

# @frappe.whitelist()
# def get_bin(item,batch,warehouse):
# 	item_escaped = frappe.db.escape(item)
# 	batch_escaped = frappe.db.escape(batch)
# 	warehouse_escaped = frappe.db.escape(warehouse)

# 	data = frappe.db.sql(
# 		"""SELECT bin_location 
# 		   FROM `tabitem bin location` 
# 		   WHERE parent = {0} 
# 		   AND batch_no = {1} 
# 		   AND warehouse = {2}"""
# 		.format(item_escaped, batch_escaped, warehouse_escaped),
# 		as_dict=True
# 	)

# 	lst = [" "]
# 	for d in data:
# 		lst.append(d.bin_location)
# 	return lst
	
@frappe.whitelist()
def update_row(item,batch,warehouse,bin_location_name):
	data=frappe.db.sql(""" select stored_qty,stored_in,length,height,width,area_use,sub_customer from `tabitem bin location` where parent="{0}"  and batch_no="{1}" and warehouse="{2}" and bin_location='{3}' """.format(item,batch,warehouse,bin_location_name),as_dict=True)
	return data
# @frappe.whitelist()
# def get_stock(self,item):
# 	is_batch=is_batch_item(item)
# 	if is_batch:
# 		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 and expiry>=now() order by expiry asc,stored_qty ASC""".format(item),as_dict=1)
# 	else:
# 		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 order by stored_qty ASC """.format(item),as_dict=1)
# 	return stk

def is_batch_item(item_code):
	has_batch_no = frappe.get_value('Item', item_code, 'has_batch_no')
	return has_batch_no 


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
	source_doc = frappe.get_doc("Preparation Order Note", source_name)


	source_doc.validate_scanned()


	def set_missing_values(source, target):
		delivery_note = frappe.get_doc(target)
	doclist = get_mapped_doc("Preparation Order Note", source_name, {
		"Preparation Order Note": {
			"doctype": "Delivery Note",
			"field_map": {
				"customer": "customer",
				"warehouse":"set_warehouse",
				"sub_customer":"sub_customer",
				"required_date":"required_date",
				"address_and_contact_details":"address_display",
				"name":"prepration",
				"delivery_request":"delivery_request"
			}
		},
		"Preparation tem":{
			"doctype": "Delivery Note Item",
			"field_map": {
				"item": "item_code",
				"item_name": "item_name",
				"uom": "uom",
				"description": "description",
				"batch_no": "batch_no",
				"warehouse": "warehouse",
				"required_date": "required_date",
				"qty_required": "quantity_required",
				"delivery_qty": "qty",
				"customer_batch_id":"customer_batch_id"
			}
		},
		"Preparation Storage Details":{
			"doctype": "Note Storage detail",
			"field_map": {
				"item": "item_code",
				"warehouse": "warehouse",
				"expiry_date": "expiry_date",
				"bin_location_name": "bin_location_name",
				"batch_no": "batch_no",
				"manufacture_date":"manufacture_date",
				"stored_in":"stored_in",
				"area_used":"area_used",
				"height": "height",
				"width": "width",
				"length":"length",
				"sub_customer":"sub_customer",
				"pallet":"pallet",

			}
		}
	}, target_doc, set_missing_values)
	return doclist

@frappe.whitelist()   
def get_item(source_name, target_doc=None):
	def set_missing_values(source, target):
		pass
	mapper = get_mapped_doc("Preparation Order Note", source_name, {
		"Preparation Order Note": {
			"doctype": "Delivery Note",
			"field_map": {
				"sub_customer":"sub_customer",
				"required_date":"required_date",
				"address_and_contact_details":"address_and_contact_details",
				
			}
		},
		"Preparation Item Grid": {
			"doctype": "Delivery Note Item",
			"field_map": {
				"item_code": "item_code",
				"item_description": "description",
				"required_date": "required_date",
				"qty_required": "quantity_required",
			}
		},
		"Preparation Storage Details": {
			"doctype": "Note Storage details",
			"field_map": {
				"item": "item_code",
				"warehouse": "warehouse",
				"expiry_date": "expiry_date",
				"bin_location_name": "bin_location_name",
				"batch_no": "batch_no",
				"expiry_date":"expiry_date",
				"delivery_qty": "delivery_qty",
				"pallet":"pallet"
			}
		}
	}, target_doc, set_missing_values)
	return mapper
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def bin_filter(doctype, txt, searchfield, start, page_len, filters):
	items = filters.get('item_code_list')
	if not items:
		return []

	placeholders = ','.join(['%s'] * len(items))

	query = f"""
		SELECT bin_location
		FROM `tabitem bin location`
		WHERE parent IN ({placeholders})
		AND bin_location LIKE %s
		LIMIT %s OFFSET %s
	"""

	args = items + [f"%{txt}%", page_len, start]
	frappe.errprint("QUERY TO EXECUTE:")
	frappe.errprint(query)
	frappe.errprint("ARGS:")
	frappe.errprint(args)


	return frappe.db.sql(query, args, as_dict=False)




