// Copyright (c) 2016, Dconnex and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Stock Report Semah"] = {
	"filters": [
		{
			"fieldname":"item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options":'Item',
		
		},
		{
			"fieldname":"item_name",
			"label": __("Item name"),
			"fieldtype": "Data",
		
		},
		{
			"fieldname":"sku",
			"label": __("SKU"),
			"fieldtype": "Data",
		
		},
		{
			"fieldname":"ware_house",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options":'Warehouse',
		
		},
		{
			"fieldname":"pallet",
			"label": __("Pallet"),
			"fieldtype": "Link",
			"options":'Pallet',
		
		},
		{
			"fieldname":"variant_of",
			"label": __("Variant of"),
			"fieldtype": "Link",
			"options":"Item"
		},
		{
			"fieldname":"item_group",
			"label": __("item group"),
			"fieldtype": "Link",
			"options":"Item Group"
		},
		{
			"fieldname":"customer",
			"label": __("Item belong to"),
			"fieldtype": "Link",
			"options":"Customer"
		},
		{
			"fieldname":"sub_customer",
			"label": __("Sub Customer"),
			"fieldtype": "Data",
		},
		{
			"fieldname":"has_variant",
			"label": __("Has variants"),
			"fieldtype": "Check",
		},
		
		
	]
};
