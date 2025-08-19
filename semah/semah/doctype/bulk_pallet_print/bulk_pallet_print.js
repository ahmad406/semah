// Copyright (c) 2025, Dconnex and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bulk Pallet Print', {
	onload: function (frm) {
		frm.trigger("options");

	},
	customer: function (frm) {
		cur_frm.set_value("sub_customer",undefined)
		frm.trigger("options");

	},
	options: function (frm) {
		if (cur_frm.doc.customer) {

			frappe.db.get_doc('Customer', cur_frm.doc.customer)
				.then(r => {
					if (r) {
						var sub = [" ",];
						var sub_customer = r.sub_customer
						for (var i = 0; i < sub_customer.length; i++) {
							sub.push(sub_customer[i].sub_customer_full_name)
						}
						frm.set_df_property("sub_customer", "options", sub);
					}
				})
		}


	},
	get_pallet: function (frm) {
		frappe.call({
			method: "get_pallet_list",
			 doc: frm.doc,
			callback: function (r) {
				if (r.message) {
					frappe.msgprint("Pallets fetched successfully");
					frm.refresh();
				}
			}

		});
	}
});
