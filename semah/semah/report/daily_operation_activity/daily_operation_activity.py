# Copyright (c) 2013, Dconnex and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _

def execute(filters=None):
    if not filters:
        return [], []
    
    conditions, values = get_conditions(filters)
    
    sql = """
        SELECT * FROM `tabDaily Operation Activity` i
        WHERE i.docstatus = 1 {0}
    """.format(conditions)

    raw = frappe.db.sql(sql, values, as_dict=True)
    
    if raw:
        columns = get_columns()
        return columns, raw
    
    return [], []

def get_conditions(filters):
    conditions = []
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("i.date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.get("from_date")
        values["to_date"] = filters.get("to_date")
    
    if filters.get("customer"):
        conditions.append("i.customer = %(customer)s")
        values["customer"] = filters.get("customer")
    
    if filters.get("sub_customer"):
        conditions.append("i.sub_customers LIKE %(sub_customer)s")
        values["sub_customer"] = f"%{filters.get('sub_customer')}%"
    
    return (" AND " + " AND ".join(conditions) if conditions else ""), values

def get_columns():
    meta = frappe.get_meta("Daily Operation Activity")
    columns = [
        {
            "label": _(field.label),
            "fieldname": field.fieldname,
            "fieldtype": field.fieldtype,
            "options": field.options,
            "width": field.width or 150  
        }
        for field in meta.fields if field.fieldname != "naming_series"
    ]
    return columns
