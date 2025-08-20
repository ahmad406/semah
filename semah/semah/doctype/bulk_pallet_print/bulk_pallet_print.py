# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
 
class BulkPalletPrint(Document):
	@frappe.whitelist()
	def get_pallet_list(self):
		cond = self.get_cond()
		sql = """
			SELECT 
				c.item_name,
				c.bin_location,
				c.pallet
			FROM `tabStock Entry` p
			INNER JOIN `tabStorage details` c ON p.name = c.parent
			WHERE p.docstatus = 1 {cond}
		""".format(cond=cond)
		

		self.set("storage_details", [])
		for d in frappe.db.sql(sql, as_dict=True):
			row = self.append("storage_details")
			row.item_name = d.item_name
			row.bin_location = d.bin_location
			row.pallet = d.pallet
		return True


	def get_cond(self):
		cond = ""
		if not self.company:
			frappe.throw("Company is mandatory")
		if not self.customer:
			frappe.throw("Customer is mandatory")
		if not self.from_date:
			frappe.throw("From Date is mandatory")
		if not self.to_date:
			frappe.throw("To Date is mandatory")

		cond += " AND p.company = {0}".format(frappe.db.escape(self.company))
		cond += " AND p.customer_nm = {0}".format(frappe.db.escape(self.customer))
		cond += " AND p.posting_date BETWEEN {0} AND {1}".format(
    frappe.db.escape(self.from_date), frappe.db.escape(self.to_date)
)



		if self.sub_customer:
			cond += " AND p.sub_customer = {0}".format(frappe.db.escape(self.sub_customer))

		return cond
