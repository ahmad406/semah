import frappe
from frappe.model.document import Document
from frappe import _

def validate(self,method=None):
    validate_change(self)
    validate_manufacturing_date(self)
    # if self.item and self.expiry_date:
    #     if frappe.db.exists("Batch", {
    #         "item": self.item,
    #         "expiry_date": self.expiry_date,
    #         "name": ["!=", self.name]
    #     }):
    #         frappe.throw(_("A batch with this item and expiry date already exists."))

def validate_manufacturing_date(self):
    if self.manufacturing_date and self.manufacturing_date > frappe.utils.today():
        frappe.throw(_("Manufacturing date cannot be in the future. It must be today or a past date."))
def validate_change(self):
    if not self.is_new():

        locked_fields = ["expiry_date", "item"]
        for field in locked_fields:
            if self.has_value_changed(field):
                frappe.throw(f"You cannot change {frappe.bold(field.replace('_', ' ').title())} after Save.")

