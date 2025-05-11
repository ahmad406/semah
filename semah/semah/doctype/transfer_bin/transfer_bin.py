# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TransferBin(Document):

	def vaidate(self):
		self.validate_mandatory()
		self.check_if_prepration_order_note()
		self.validate_transfer()


	@frappe.whitelist()
	def show_bin_info(self):
		def get_bin_details(bin_name, field_prefix):
			# Using parameterized query to prevent SQL injection
			data = frappe.db.sql("""
				select 
					pallet, 
					item_code, 
					bin_location, 
					stored_qty, 
					expiry, 
					warehouse 
				from `tabItem Bin Location` 
				where bin_location = %s and stored_qty > 0
				limit 2  # We only need to check for single/multiple records
			""", bin_name, as_dict=1)
			
			if not data:
				return ""
			elif len(data) > 1:
				frappe.throw(f"Multiple records found for bin {bin_name}")
			
			item_name = frappe.get_cached_value('Item', data[0]['item_code'], 'item_name')
			
			return f"""
				<div class="bin-info">
					<p><strong>Pallet:</strong> {data[0]['pallet']}</p>
					<p><strong>Item:</strong> {item_name}</p>
					<p><strong>Bin Location:</strong> {data[0]['bin_location']}</p>
					<p><strong>Qty:</strong> {data[0]['stored_qty']}</p>
					<p><strong>Expiry:</strong> {data[0]['expiry'] or 'N/A'}</p>
					<p><strong>Warehouse:</strong> {data[0]['warehouse']}</p>
				</div>
			"""

		if self.source_bin:
			self.source_detail = get_bin_details(self.source_bin, "source")
		
		if self.target_bin:
			self.target_detail = get_bin_details(self.target_bin, "target")
		return True

	def validate_mandatory(self):
		if not self.source_bin:
			frappe.throw("Source Bin is missing..!")
		if not self.target_bin:
			frappe.throw("Target Bin is missing..!")
		if self.target_bin==self.source_bin:
			frappe.throw("Target and Source Bin can't be same")
	def check_if_prepration_order_note(self):
		sql="""select p.name from `tabPreparation Order Note` p 
			inner join `tabPreparation Storage Details` c on p.name=c.parent 
			where bin_location_name="{0}" 
			and order_status='To make Delivery Note' 
			and docstatus=1 """.format(self.source_bin)
		data = frappe.db.sql(sql, as_dict=1)
		if data:
			frappe.throw("Preparation Order Note already created against this bin: {0}".format(data[0]['name']))
	def validate_transfer(self):
		target=frappe.get_doc("Bin Name",self.target)
		if target.status=="Occupied":
			frappe.throw("Target Bin is already Occupied")

	def submit(self):
		sql="""select name from `tabitem bin location` where bin_location = "{0}" and stored_qty > 0 """.format(self.source_bin)
		data=frappe.db.sql(sql,as_dict=1)
		if len(data)!=1:
			frappe.throw("multiple record found")
		else:
			bn=frappe.get_doc("Bin Name",data[0].name)
			bn.db_set("bin_location",self.target_bin)


