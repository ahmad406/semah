# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BinBulkPrint(Document):
	@frappe.whitelist()
	def set_bin(self):
		if self.warehouse:
			self.set("bulk_bin", [])
			
			conditions = ['warehouse = %s']
			values = [self.warehouse]

			if self.bin_row:
				conditions.append('bin_row = %s')
				values.append(self.bin_row)

			condition_str = " and ".join(conditions)
			sql = f"""SELECT name FROM `tabBin Name` WHERE {condition_str}"""
			
			data = frappe.db.sql(sql, values, as_dict=1)
			for d in data:
				row = self.append("bulk_bin", {})
				row.bin_name = d.name

		return True
