# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BinBulkPrint(Document):
	@frappe.whitelist()
	def set_bin(self):
		if self.warehouse:
			self.set("bulk_bin",[])
			sql="""select name from `tabBin Name` where warehouse="{}" """.format(self.warehouse)
			data=frappe.db.sql(sql,as_dict=1)
			for d in data:
				row=self.append("bulk_bin",{})
				row.bin_name=d.name
		return True
