# Copyright (c) 2025, Dconnex and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class StockBinandPalletScanner(Document):
	@frappe.whitelist()
	def show_bin_info(self):

		Type = ""
		if frappe.db.exists("Bin Name", self.source_bin):
			Type = "Bin"
		elif frappe.db.exists("Pallet", self.source_bin):
			Type = "Pallet"
		else:
			frappe.throw("Bin or Pallet not found.")
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

			elif field_prefix == "Pallet":
				data = frappe.db.sql("""
					select 
						pallet, 
						parent item_code, 
						bin_location, 
						stored_qty, 
					DATE_FORMAT(expiry, '%d-%m -%Y') AS expiry, 
						warehouse 
					from `tabitem bin location` 
					where pallet ="{0}" and stored_qty > 0
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
			return data
		else:
			frappe.msgprint("Scan Properly")
			return "No Show"
