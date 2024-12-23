# Copyright (c) 2022, Dconnex and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document

class DeliveryRequest(Document):
	def on_cancel(self):
		frappe.db.sql("""update  `tabDelivery Request` set doc_status="Cancelled" 
		 where name="{0}" """.format(self.name))
	
	@frappe.whitelist()
	def calculate_total(self):
		total=0
		for d in self.item_grid:
			if d.qty_required:
				total+=d.qty_required
		self.set("total_qty",total)


@frappe.whitelist()
def make_preparation_order_note(source_name, target_doc=None):
	def set_missing_values(source, target):
		preperation_order_note = frappe.get_doc(target)
	doclist = get_mapped_doc("Delivery Request", source_name, {
		"Delivery Request": {
			"doctype": "Preparation Order Note",
			"field_map": {
				"customer": "customer",
				"sub_customer": "sub_customer",
				"required_date": "required_date",
                "requested_date": "requested_date",
				"warehouse": "warehouse",
                "address_html": "customer_primary_address",
                "address_and_contact_details": "address_and_contact_details"
			}
		},
		"Item Grid":{
			"doctype": "Preparation Item Grid",
			"field_map": {
				"item_code": "item_code",
                "item_name": "item_name",
				"item_description": "item_description",
				"required_date": "required_date",
				"qty_required": "qty_required",
                "uom": "uom"
			}
		}
	}, target_doc, set_missing_values)
	return doclist


@frappe.whitelist()   
def get_item(source_name, target_doc=None):
	def set_missing_values(source, target):
		pass
	mapper = get_mapped_doc("Delivery Request", source_name, {
		"Delivery Request": {
			"doctype": "Preparation Order Note",
		},
		"Item Grid": {
			"doctype": "Preparation Item Grid",
			"field_map": {
				"item_code": "item_code",
                "item_name": "item_name",
				"item_description": "item_description",
				"required_date": "required_date",
				"qty_required": "qty_required",
                "uom": "uom"
			}
	}
	}, target_doc, set_missing_values)
	return mapper

@frappe.whitelist()
def item_query(customer_,sub_customer):
	#frappe.errprint("""select i.name from `tabItem` as i
	#left join `tabitem bin location` as j on (j.parent=i.name)
	#where i.customer_='{0}' and j.sub_customer='{1}'""".format(filters.get('customer_'),filters.get('sub_customer')))
	return frappe.db.sql("""select distinct i.name  from `tabItem` as i
	  join `tabitem bin location` as j on (j.parent=i.name)
	  where i.customer_='{0}'  and j.sub_customer='{1}' 
	  union
	  select distinct m.name from `tabItem` as m
	  left  join `tabitem bin location` as n on (n.parent=m.name)
	  where m.customer_='{0}' and 
	  not exists   (
		  select 1 from `tabItem` as k
		  left join `tabitem bin location` as l on (l.parent=k.name)
		  where k.customer_='{0}'  and l.sub_customer='{1}' )""".format(customer_,sub_customer),as_dict=1)


	#return frappe.db.sql("""select i.name ,j.sub_customer from `tabItem` as i
	#left join `tabitem bin display` as j on (j.parent=i.name)
	#where i.customer_='{0}' and j.sub_customer='{1}' """.format(filters.get('customer_'),filters.get('sub_customer')))

	
   