// Copyright (c) 2016, Dconnex and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Daily Operation Activity"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
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
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
	
	],
	
}