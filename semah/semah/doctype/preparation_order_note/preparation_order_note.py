# Copyright (c) 2022, Dconnex and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document

from collections import defaultdict
from frappe.utils import flt

class PreparationOrderNote(Document):
	def on_submit(self):
		frappe.db.sql("""update  `tabDelivery Request` set doc_status="To Make Delivery Note"
		where name="{0}" """.format(self.delivery_request))
		self.validate_scanned()

	def on_cancel(self):
		frappe.db.sql("""update  `tabPreparation Order Note` set order_status="Cancelled"
		where name="{0}" """.format(self.name))
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




	def validate_scanned(self):
		scanned_map = defaultdict(float)
		for d in self.scanned_items:
			key = (d.item, d.pallet)
			scanned_map[key] += flt(d.delivery_qty)

		storage_map = defaultdict(float)
		for d in self.storage_details:
			key = (d.item, d.pallet)
			storage_map[key] += flt(d.delivery_qty)

		for key in storage_map:
			if key not in scanned_map:
				frappe.throw(f"Item {key[0]} Pallet {key[1]} exists in Storage but not in Scanned Items.")

			if flt(scanned_map[key]) != flt(storage_map[key]):
				frappe.throw(f"Mismatch in Delivery Qty for Item {key[0]}, Pallet {key[1]}: "
							f"Scanned = {scanned_map[key]}, Storage = {storage_map[key]}")

		for key in scanned_map:
			if key not in storage_map:
				frappe.throw(f"Item {key[0]} Pallet {key[1]} exists in Scanned but not in Storage.")


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
		if not self.is_bulk_entry:
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


					return True



	@frappe.whitelist()
	def add_item_in_storage(self,insert=None):
		self.source_bin = self.barcode
		Type = ""

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
						c.area_use, c.stored_qty, c.manufacturing_date, c.pallet
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
						c.area_use, c.stored_qty, c.manufacturing_date, c.pallet
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


			return data
		else:
			frappe.msgprint("Scan properly.")
			return "No Show"

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
@frappe.whitelist()
def get_stock(item):
	is_batch=is_batch_item(item)
	if is_batch:
		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 and expiry>=now() order by expiry asc,stored_qty ASC""".format(item),as_dict=1)
	else:
		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 order by stored_qty ASC """.format(item),as_dict=1)
	return stk

def is_batch_item(item_code):
	has_batch_no = frappe.get_value('Item', item_code, 'has_batch_no')
	return has_batch_no 


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None):
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
