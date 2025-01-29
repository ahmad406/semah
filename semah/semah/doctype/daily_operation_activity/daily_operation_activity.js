

frappe.ui.form.on('Daily Operation Activity', {
	refresh: function(frm) {
		frm.trigger("options")
	},
	customer: function (frm) {
		frm.trigger("options")
	},
	options: function (frm) {
		if (cur_frm.doc.customer){

			frappe.db.get_doc('Customer', cur_frm.doc.customer)
			.then(r => {
				if (r) {
					var sub = [" ",];
					var sub_customer = r.sub_customer
					for (var i = 0; i < sub_customer.length; i++) {
						sub.push(sub_customer[i].sub_customer_full_name)
					}
					frm.set_df_property("sub_customers", "options", sub);
				}
			})
		}


	},
});
