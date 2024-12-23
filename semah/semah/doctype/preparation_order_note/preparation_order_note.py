# Copyright (c) 2022, Dconnex and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document

class PreparationOrderNote(Document):
	def on_submit(self):
		frappe.db.sql("""update  `tabDelivery Request` set doc_status="To Make Delivery Note"
		where name="{0}" """.format(self.delivery_request))

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

@frappe.whitelist()
def get_delivery_request(customer):
	data=frappe.db.sql("""select dr.name,dr.customer  from `tabDelivery Request` as dr 
	 where dr.customer="{0}"  and dr.docstatus=1 and dr.doc_status="To make Preparation Order" order by dr.creation  desc """.format(customer),as_dict=True)
	return data
@frappe.whitelist()
def get_bin(item,batch,warehouse):
	data=frappe.db.sql(""" select bin_location from `tabitem bin location` where parent="{0}"  and batch_no="{1}" and warehouse="{2}" """.format(item,batch,warehouse),as_dict=True)
	# frappe.errprint("""select bin_location from `tabitem bin location` where parent="{0}"  and batch_no="{1}" and warehouse="{3}" """.format(item,batch,warehouse))
	lst=[" "]
	for d in data:
		lst.append(d.bin_location)
	
	return lst
@frappe.whitelist()
def update_row(item,batch,warehouse,bin_location_name):
	data=frappe.db.sql(""" select stored_qty,stored_in,length,height,width,area_use,sub_customer from `tabitem bin location` where parent="{0}"  and batch_no="{1}" and warehouse="{2}" and bin_location='{3}' """.format(item,batch,warehouse,bin_location_name),as_dict=True)
	return data

@frappe.whitelist()
def get_stock(item):
	is_batch=is_batch_item(item)
	if is_batch:
		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 and expiry>=now() order by expiry asc""".format(item),as_dict=1)
	else:
		stk= frappe.db.sql("""select * from `tabitem bin location` where parent="{0}"  and stored_qty!=0 """.format(item),as_dict=1)
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
				"delivery_qty": "delivery_qty"
			}
		}
	}, target_doc, set_missing_values)
	return mapper
