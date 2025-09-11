import frappe

def validate(doc, method=None):
    if doc.cost_center:
        for d in doc.items:
            d.cost_center = doc.cost_center

        for t in doc.taxes:
            t.cost_center = doc.cost_center
