# Copyright (c) 2013, Dconnex and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _

def execute(filters=None):
	conditions= get_conditions(filters)
	sql = """				
		select CONCAT(posting_date, ' ', posting_time) as date ,sub_customer,customer_ as customer ,sle.item_code,i.item_name,sle.stock_uom,actual_qty,
		warehouse,batch_no,qty_after_transaction,customer_batch_id,manufacturing_date,expiry_date,voucher_type,voucher_no from `tabStock Ledger Entry` sle
		inner join `tabItem` i on sle.item_code=i.name 
		left join `tabBatch` b on sle.batch_no=b.name where posting_date  BETWEEN '{0}' AND '{1}' {2} order by sle.creation 
		""".format(filters.get("from_date"),filters.get("to_date"),conditions)
	raw =frappe.db.sql(sql,as_dict=1)
	frappe.errprint(sql)
	result=[]
	if len(raw)!=0:
		for idx, i in enumerate(raw):
			
				
			result.append({
						"date":i.date ,
						"item_code":i.item_code ,
						"item_name" :i.item_name ,
						"stock_uom" : i.stock_uom ,
						"item_belong" :i.customer  ,
						"in_qty" : i.actual_qty if i.actual_qty >0 else 0 ,
						"out_qty" : i.actual_qty if i.actual_qty <0 else 0 ,
						"qty_after_transaction": i.qty_after_transaction,
						"sub_customer" : i.sub_customer ,
						"warehouse" : i.warehouse,
						"batch" :i.customer_batch_id if  i.customer_batch_id else i.batch_no,
						"menufac_date" : i.manufacturing_date,
						"exp_date" : i.expiry_date,
						"voucher_type":i.voucher_type,
						"voucher_no":i.voucher_no
				})

		columns = get_columns()
		return columns, result
	return [],[]

def get_conditions(filters):
	conditions=""
	if filters.get("item_code"):
		conditions=conditions+' and sle.item_code="{0}" '.format(filters.get("item_code"))
	if filters.get("warehouse"):
		conditions=conditions+' and sle.warehouse="{0}" '.format(filters.get("warehouse"))
	if filters.get("customer"):
		conditions=conditions+' and i.customer_="{0}" '.format(filters.get("customer"))
	if filters.get("sub_customer"):
		conditions=conditions+' and i.sub_customer like "%{0}%" '.format(filters.get("sub_customer"))
	if filters.get("include_uom"):
		conditions=conditions+' and sle.stock_uom= "{0}" '.format(filters.get("include_uom"))
	if filters.get("voucher_no"):
		conditions=conditions+' and sle.voucher_no like "%{0}%" '.format(filters.get("voucher_no"))
	return conditions



def get_columns():
	columns = [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 120},
		{"label": _("Item belong"), "fieldname": "item_belong", "fieldtype": "Link","options":"Customer" ,"width": 180},
		{"label": _("Sub Customer"), "fieldname": "sub_customer", "fieldtype": "Data", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 100},
		{"label": _("Item Name"), "fieldname": "item_name", "width": 100},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Balance Qty"), "fieldname": "qty_after_transaction", "fieldtype": "Float", "width": 80, "convertible": "qty"},
		{"label": _("Voucher #"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 110,"hidden":1},
		{"label": _("Batch"), "fieldname": "batch", "fieldtype": "Data", "width": 200},
		{"label": _("Manufacturing Date"), "fieldname": "menufac_date", "fieldtype": "Date", "width": 180},
		{"label": _("Expiry Date"), "fieldname": "exp_date",  "fieldtype": "Date","width": 180},
	]

	return columns


