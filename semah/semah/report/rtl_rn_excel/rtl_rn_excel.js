// Copyright (c) 2016, Dconnex and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["RTL RN Excel"] = {
  "filters": [
    {
      "fieldname": "from_date",
      "label": "From Date",
      "fieldtype": "Date",
      "default": "Today",
      "reqd": 1
    },
    {
      "fieldname": "to_date",
      "label": "To Date",
      "fieldtype": "Date",
      "default": "Today",
      "reqd": 1
    },
    {
      "fieldname": "customer_nm",
      "label": "Item belong to",
      "fieldtype": "Link",
      "options": "Customer"
    },
    {
      "fieldname": "sub",
      "label": "Sub Customer",
      "fieldtype": "Data"
    },
    {
      "fieldname": "name",
      "label": "Stock Entry ID",
      "fieldtype": "Data"
    }
  ]
}

