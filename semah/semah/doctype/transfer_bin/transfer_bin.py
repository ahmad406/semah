# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TransferBin(Document):

	def validate(self):
		self.validate_mandatory()
		self.check_if_prepration_order_note()
		self.validate_transfer()


	@frappe.whitelist()
	def show_bin_info(self):

		Type = ""
		if frappe.db.exists("Bin Name", self.source_bin):
			Type = "Bin"
		else:
			frappe.throw("Bin  not found.")
		def get_bin_details(bin_name, field_prefix):
			if field_prefix == "Bin":
				data = frappe.db.sql("""
					select 
						pallet, 
				parent	item_code, 
						bin_location, 
						stored_qty, 
					DATE_FORMAT(expiry, '%d-%m-%Y') AS expiry, 
						warehouse 
					from `tabitem bin location` 
					where bin_location = "{0}" and stored_qty > 0
					limit 2
				""".format(bin_name), as_dict=1)

			else:
				return ""

			if not data:
				return ""

			if len(data) > 1:
				frappe.msgprint(f"Multiple records found for {field_prefix} {bin_name}")
				return "No Show"


			item_name = frappe.get_cached_value('Item', data[0]['item_code'], 'item_name')
			

			return  f"""
			<div class="bin-info-container" style="
				font-family: 'Segoe UI', Arial, sans-serif;
				max-width: 500px;
				margin: 10px;
				border-radius: 8px;
				box-shadow: 0 2px 8px rgba(0,0,0,0.1);
				overflow: hidden;
				background: #f9f9f9;
			">
				<div class="bin-header" style="
					background: #2c3e50;
					color: white;
					padding: 12px 15px;
					font-size: 18px;
					font-weight: bold;
				">
					{Type} Information
				</div>
				
				<div class="bin-details" style="padding: 15px;">
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 10px;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Pallet:
						</div>
						<div class="detail-value" style="flex: 1;">
							{data[0]['pallet']}
						</div>
					</div>
					
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 10px;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Item:
						</div>
						<div class="detail-value" style="flex: 1;">
							{item_name}
						</div>
					</div>
					
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 10px;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Bin Location:
						</div>
						<div class="detail-value" style="
							flex: 1;
							font-weight: bold;
							color: #e74c3c;
						">
							{data[0]['bin_location']}
						</div>
					</div>
					
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 10px;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Quantity:
						</div>
						<div class="detail-value" style="
							flex: 1;
							font-weight: bold;
							color: #27ae60;
						">
							{data[0]['stored_qty']}
						</div>
					</div>
					
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 10px;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Expiry:
						</div>
						<div class="detail-value" style="
							flex: 1;
							color: { '#e67e22' if data[0]['expiry'] else '#7f8c8d' };
							font-weight: { 'bold' if data[0]['expiry'] else 'normal' };
						">
							{data[0]['expiry'] or 'N/A'}
						</div>
					</div>
					
					<div class="detail-row" style="
						display: flex;
						margin-bottom: 0;
						align-items: center;
					">
						<div class="detail-label" style="
							flex: 0 0 120px;
							font-weight: 600;
							color: #555;
						">
							Warehouse:
						</div>
						<div class="detail-value" style="flex: 1;">
							{data[0]['warehouse']}
						</div>
					</div>
				</div>
				
				<div class="bin-footer" style="
					background: #ecf0f1;
					padding: 8px 15px;
					text-align: right;
					font-size: 12px;
					color: #7f8c8d;
				">
					Last updated: {frappe.utils.now_datetime().strftime('%Y-%m-%d %H:%M')}
				</div>
			</div>
			"""

		if self.source_bin:
			data = get_bin_details(self.source_bin, Type)
			self.set("source_det",data)
			return data
		else:
			frappe.msgprint("Scan Properly")
			return "No Show"


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
			and p.docstatus=1 """.format(self.source_bin)
		data = frappe.db.sql(sql, as_dict=1)
		if data:
			frappe.throw("Preparation Order Note already created against this bin: {0}".format(data[0]['name']))
	def validate_transfer(self):
		target=frappe.get_doc("Bin Name",self.target_bin)
		if target.status=="Occupied":
			frappe.throw("Target Bin is already Occupied :{}".format(self.target_bin))
		source=frappe.get_doc("Bin Name",self.source_bin)
		if source.status=="Vacant":
			frappe.throw("Source Bin is Vacant :{}".format(self.source_bin))

	def on_submit(self):
		sql="""select name from `tabitem bin location`   where bin_location = "{0}" and stored_qty > 0 """.format(self.source_bin)
		data=frappe.db.sql(sql,as_dict=1)
		if data:
			if len(data)>1:
				frappe.throw("Multiple Record Found")
			else:
				bn=frappe.get_doc("item bin location",data[0].name)
				bn.db_set("bin_location",self.target_bin)
				bin_t=frappe.get_doc("Bin Name",self.target_bin)
				bin_t.db_set("status","Occupied")
				bin_s=frappe.get_doc("Bin Name",self.source_bin)
				bin_s.db_set("status","Vacant")

				# frappe.db.commit()
		else:
			frappe.throw("Source Bin is Vacant")



