# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BinName(Document):
	def validate(self):
		if self.bin_row:
			if not frappe.db.exists("Bin Row", self.bin_row):
				bin=frappe.new_doc("Bin Row")
				bin.bin_row=self.bin_row
				bin.save()

