import frappe
from frappe.utils import add_days, getdate,nowdate,flt
from frappe import _
def validate(self, method=None):
    if self.voucher_type != "Stock Entry" or not self.voucher_detail_no:
        return

    se = frappe.get_doc("Stock Entry Detail", self.voucher_detail_no)

    for d in self.entries:
        if not d.batch_no:
            continue

        batch = frappe.get_doc("Batch", d.batch_no)

        if batch.reference_name != self.voucher_no:
            continue

        batch.db_set({
            "manufacturing_date": se.manufacturing_date,
            "expiry_date": se.expiry
        })


