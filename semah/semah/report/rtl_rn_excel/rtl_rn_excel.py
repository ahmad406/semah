import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    conditions = []
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions.append("se.posting_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = filters["to_date"]

    if filters.get("customer_nm"):
        conditions.append("se.customer_nm = %(customer_nm)s")
        values["customer_nm"] = filters["customer_nm"]

    if filters.get("sub"):
        conditions.append("se.sub LIKE %(sub)s")
        values["sub"] = f"%{filters['sub']}%"

    if filters.get("name"):
        conditions.append("se.name = %(name)s")
        values["name"] = filters["name"]

    condition_str = " AND " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT
            se.name AS name,
            se.docstatus AS docstatus,
            se.sub AS sub,
            i.sku AS sku,
            sd.item_code AS item_code,
            sd.item_description AS item_name,
            i.stock_uom AS uom,
            sd.stored_qty AS stored_qty,
            sd.manufacture AS manufacture,
            sd.expiry AS expiry,
            sd.bin_location AS bin_location,
            sd.pallet AS pallet
        FROM
            `tabStock Entry` se
        INNER JOIN `tabStorage details` sd ON sd.parent = se.name
        LEFT JOIN `tabItem` i ON i.item_code = sd.item_code
        WHERE
            se.docstatus = 1
            {condition_str}
        ORDER BY
            se.modified DESC
    """

    data = frappe.db.sql(query, values, as_dict=1)

    columns = [
        {"label": "Stock Entry ID", "fieldname": "name", "fieldtype": "Link", "options": "Stock Entry", "width": 150},
        {"label": "Docstatus", "fieldname": "docstatus", "fieldtype": "Int", "width": 80,"hidden":1},
        {"label": "Sub Customer", "fieldname": "sub", "fieldtype": "Data", "width": 150},
        {"label": "SKU", "fieldname": "sku", "fieldtype": "Data", "width": 120},
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Item Description", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 100},
        {"label": "Stored Qty", "fieldname": "stored_qty", "fieldtype": "Float", "width": 120},
        {"label": "Manufacture Date", "fieldname": "manufacture", "fieldtype": "Date", "width": 120},
        {"label": "Expiry Date", "fieldname": "expiry", "fieldtype": "Date", "width": 120},
        {"label": "Bin Location", "fieldname": "bin_location", "fieldtype": "Data", "width": 150},
        {"label": "Pallet", "fieldname": "pallet", "fieldtype": "Data", "width": 150}
    ]

    return columns, data

