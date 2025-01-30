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
				if value is not None and value < 0:
					field_label = self.meta.get_field(fieldname).label
					frappe.throw(f"{field_label} must be positive")


