# Copyright (c) 2013, Dconnex and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
import re

def execute(filters=None):
	if not filters:
		return [], []	
	conditions= get_conditions(filters)
	frappe.errprint(conditions)
	# if filters.get("item_code") and not filters.get("warehouse") and not filters.get("customer") and not  filters.get("sub_customer"):
	# 	conditions=" and p.item_code='{0} ".format(filters.get("item_code"))
	# elif filters.get("warehouse") and not filters.get("item_code") and not filters.get("customer") and not  filters.get("sub_customer"):
	# 	conditions.append(' and c.Ware_house="{0}" '.format(filters.get("warehouse")))
	# elif filters.get("customer") and not filters.get("item_code") and not filters.get("warehouse") and not  filters.get("sub_customer"):
	# 	conditions.append(' and p.customer_="{0}"" '.format(filters.get("customer")))
	# elif filters.get("sub_customer") and not filters.get("item_code") and not filters.get("warehouse") and not  filters.get("sub_customer"):
	# 	conditions.append(' and c.sub_customer like "%{0}%" '.format(filters.get("customer")))

	sql = """				
	 select  p.customer_ as customer,p.stock_uom,p.item_name,p.sku,p.disabled,p.name as item_code,b.customer_batch_id,c.batch_no as batch,c.sub_customer,c.warehouse,p.has_batch_no,c.bin_location,c.batch_no,c.expiry,c.stored_in,c.length,c.width,c.height,c.area_use,c.stored_qty,c.manufacturing_date from `tabitem bin location` c
 inner join `tabItem` p on c.parent=p.name
 left join `tabBatch` b on c.batch_no=b.name where c.stored_qty >0 {0}
	""".format(conditions)
	frappe.errprint(sql)
	raw =frappe.db.sql(sql,as_dict=1)
	result=[]
	frappe.errprint(raw)
	if len(raw)!=0:
		for idx, i in enumerate(raw):

			result.append({
						"item_code":i.item_code,
						"sku":i.sku ,
						"status" :"Disable" if i.disabled  else "Enable",
						"item_name" :i.item_name ,
						"uom" : i.stock_uom ,
						"item_belong" :i.customer  ,
						"has_batch" : i.has_batch_no ,
						"sub_customer" : i.sub_customer ,
						"warehouse" : i.warehouse,
						"bin_location" : i.bin_location,
						"batch" :i.customer_batch_id if  i.customer_batch_id else i.batch,
						"menufac_date" : i.manufacturing_date,
						"exp_date" : i.expiry,
						"stored_qty" : i.stored_qty,
						"stored_in" : i.stored_in,
						"length" : i.length,
						"height" : i.height,
						"width" : i.width,
						"area_used" :i.area_use,
				})

		columns = get_columns()
		return columns, result
	return [],[]

def get_conditions(filters):
	conditions=""
	if filters.get("item_code"):
		conditions=conditions+' and p.item_code="{0}" '.format(filters.get("item_code"))
	if filters.get("ware_house"):
		frappe.errprint(filters.get("warehouse"))
		conditions=conditions+' and warehouse="{0}" '.format(filters.get("ware_house"))
	if filters.get("customer"):
		conditions=conditions+' and p.customer_="{0}" '.format(filters.get("customer"))
	if filters.get("sub_customer"):
		conditions=conditions+' and c.sub_customer like "%{0}%" '.format(filters.get("sub_customer"))
	if filters.get("item_group"):
		conditions=conditions+' and p.item_group = "{0}" '.format(filters.get("item_group"))
	if filters.get("has_variant"):
		conditions=conditions+' and p.has_variants = "{0}" '.format(filters.get("has_variant"))
	if filters.get("variant_of"):
		conditions=conditions+' and p.variant_of = "{0}" '.format(filters.get("variant_of"))
	if filters.get("item_name"):
		conditions=conditions+' and p.item_name like "%{0}%" '.format(filters.get("item_name"))
	if filters.get("sku"):
		conditions=conditions+' and p.sku like "%{0}%" '.format(filters.get("sku"))
	return conditions



def get_columns():
	columns=[]

	columns+= [
		{
	 		'fieldname': 'item_code',
            'label':('Item code'),
            'fieldtype': 'Link',
            'options': 'Item',
			'width': 170
        },
		{
	 		'fieldname': 'sku',
            'label':('SKU'),
            'fieldtype': 'Data',
			'width': 220
        },
		{
	 		'fieldname': 'item_name',
            'label':('Item Name'),
            'fieldtype': 'Data',
			'width': 220
        },
			{
			'label': _('Batch'),
			'fieldname': "batch",
			'fieldtype': 'Data',
			'width': 120,
	
		},
			{
			'label': _('Manufacturing Date'),
			'fieldname':"menufac_date",
			'fieldtype': 'Date',
			'width': 120
		},
		{
			'fieldname':"exp_date",
            'label': ('Expiry Date'),
            'fieldtype': 'Date',
			'width':160

		},
		{
	 		'fieldname': "stored_qty" ,
            'label':('Stored Qty'),
            'fieldtype': 'Float',
			'width': 200
        },
		{
			'label': _('Default unit of measurement'),
			'fieldname': "uom",
			'fieldtype': 'Data',
			'width': 120
		},
      
		{
			'label': _('Item Belong to'),
			'fieldname':  "item_belong",
			'fieldtype': 'Link',
			'options': 'Customer',
			'width': 120
		},
		
		{
			'label': _('Sub Customer'),
			'fieldname': "sub_customer",
			'fieldtype': 'Data',
			'width': 120
		},
		 
			{
			'label': _('Warehouse'),
			'fieldname': "warehouse",
			'fieldtype': 'Link',
			'options':'Warehouse',
			'width': 150,
		},
			{
			'label': _('Bin Location'),
			'fieldname': "bin_location",
			'fieldtype': 'Data',
			'width': 150,
		},
		{
	 		'fieldname': "length",
            'label':('Length'),
            'options': 'Customer',
			'width': 150
        },
			{
	 		'fieldname': "height",
            'label':('Height'),
            'fieldtype': 'Float',
			'width': 150
        },
		{
	 		'fieldname': "width",
            'label':('Width'),
            'fieldtype': 'Float',
			'width': 120
        },
			{
	 		'fieldname': "area_used",
            'label':('Area used'),
            'fieldtype': 'Float',
			'width': 120
        },
		#  {
        #     'fieldname': "status",
        #     'label': ('Status'),
        #     'fieldtype': 'Data',
        # },
		# {
		# 	'label': _('Has Batch No'),
		# 	'fieldname':"has_batch",
		# 	'fieldtype': 'Check',
		# 	'width': 120
		# },
		#   {
        #     'fieldname': "stored_in",
        #     'label': ('Stored in'),
        #     'fieldtype': 'Data',
		# 	'width': 120

        # },

	]



	
	return columns

	