# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class DailyOperationActivity(Document):
	def validate(self):
		for field in self.meta.get("fields"):
			# frappe.errprint(field.as_dict())

			if field.fieldtype == "Float":
				fieldname = field.fieldname
				value = self.get(fieldname)
				if value is not None and value <= 0:
					frappe.throw(f"{field.label} must be greater than 0.")

