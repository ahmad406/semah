// Copyright (c) 2025, Dconnex and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bin Bulk Print', {
	setup: function (frm) {
		frm.set_query("warehouse", function () {
			return {
				filters: {
					"is_group": 1
				}
			};
		});

	},
	warehouse:function(frm){

		frappe.call({
			method: "set_bin",
			doc: cur_frm.doc,
            callback: function(r) {
				if (r.message) {
					cur_frm.refresh()
				}
            }
        });
	},
	bin_row:function(frm){

		frappe.call({
			method: "set_bin",
			doc: cur_frm.doc,
            callback: function(r) {
				if (r.message) {
					cur_frm.refresh()
				}
            }
        });
	}
});
