# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
    if not filters:
        filters = {}

    if filters.from_date > filters.to_date:
        frappe.throw(_("From Date must be before To Date"))

    float_precision = cint(frappe.db.get_default("float_precision")) or 3

    columns = get_columns(filters)
    item_map = get_item_details(filters)
    iwb_map = get_item_warehouse_batch_map(filters, float_precision)

    data = []
    for item in sorted(iwb_map):
        if not filters.get("item") or filters.get("item") == item:
            sub_customer = item_map[item].get("sub_customer", "")  # Fetch the sub_customer from tabItem
            for wh in sorted(iwb_map[item]):
                for batch in sorted(iwb_map[item][wh]):
                    qty_dict = iwb_map[item][wh][batch]
                    if qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty:
                        expiry_date = frappe.db.get_value('Batch', batch, 'expiry_date')
                        data.append([item, item_map[item]["item_name"], sub_customer, wh, batch, expiry_date,
                                     flt(qty_dict.bal_qty, float_precision), item_map[item]["stock_uom"]])

    if filters.get("hide_zero_qty"):
        data = [d for d in data if d[6] != 0]  # Check the Balance Qty field for zero quantity

    return columns, data




def get_columns(filters):
    """return columns based on filters"""
    columns = [_("Item") + ":Link/Item:100"] + [_("Item Name") + "::150"] + \
              [_("Sub Customer") + "::150"] + [_("Warehouse") + ":Link/Warehouse:100"] + \
              [_("Batch") + ":Link/Batch:100"] + [_("Expiry Date") + ":Date:100"] + \
              [_("Balance Qty") + ":Float:90"] + [_("UOM") + "::90"]

    return columns




def get_conditions(filters):
    conditions = ""
    if not filters.get("from_date"):
        frappe.throw(_("'From Date' is required"))

    if filters.get("to_date"):
        conditions += " and sle.posting_date <= '%s'" % filters["to_date"]
    else:
        frappe.throw(_("'To Date' is required"))

    for field in ["item_code", "warehouse", "batch_no", "company"]:
        if filters.get(field):
            conditions += " and sle.{0} = {1}".format(field, frappe.db.escape(filters.get(field)))

    if filters.get("sub_customer"):
        sub_customer = frappe.db.escape(filters.get("sub_customer"))
        conditions += " and item.sub_customer like {0}".format(sub_customer)


    return conditions



def get_stock_ledger_entries(filters):
    conditions = get_conditions(filters)
    sql_query = """
        select sle.item_code, sle.batch_no, sle.warehouse, sle.posting_date, sle.actual_qty, item.sub_customer, batch.expiry_date
        from `tabStock Ledger Entry` as sle
        left join `tabItem` as item on sle.item_code = item.name
        left join `tabBatch` as batch on sle.batch_no = batch.name
        where sle.is_cancelled = 0 and sle.docstatus < 2 and ifnull(sle.batch_no, '') != '' {0}
        order by sle.item_code, sle.warehouse
    """.format(conditions)
    # frappe.msgprint(str(sql_query))
    return frappe.db.sql(sql_query, as_dict=1)





def get_item_warehouse_batch_map(filters, float_precision):
    sle = get_stock_ledger_entries(filters)
    iwb_map = {}

    from_date = getdate(filters["from_date"])
    to_date = getdate(filters["to_date"])

    for d in sle:
        iwb_map.setdefault(d.item_code, {}).setdefault(d.warehouse, {}) \
            .setdefault(d.batch_no, frappe._dict({
            "opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0
        }))
        qty_dict = iwb_map[d.item_code][d.warehouse][d.batch_no]
        if d.posting_date < from_date:
            qty_dict.opening_qty = flt(qty_dict.opening_qty, float_precision) \
                                  + flt(d.actual_qty, float_precision)
        elif d.posting_date >= from_date and d.posting_date <= to_date:
            if flt(d.actual_qty) > 0:
                qty_dict.in_qty = flt(qty_dict.in_qty, float_precision) + flt(d.actual_qty, float_precision)
            else:
                qty_dict.out_qty = flt(qty_dict.out_qty, float_precision) \
                                   + abs(flt(d.actual_qty, float_precision))

        qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.actual_qty, float_precision)

    return iwb_map


def get_item_details(filters):
    item_map = {}
    for d in frappe.db.sql("select name, item_name, description, stock_uom, sub_customer from tabItem", as_dict=1):
        item_map.setdefault(d.name, d)

    return item_map
