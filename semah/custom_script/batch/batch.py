import frappe
from frappe.model.document import Document
from frappe import _

def validate(self,method=None):
    if self.item and self.expiry_date:
        if frappe.db.exists("Batch", {
            "item": self.item,
            "expiry_date": self.expiry_date,
            "name": ["!=", self.name]
        }):
            frappe.throw(_("A batch with this item and expiry date already exists."))
