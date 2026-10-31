// Copyright (c) 2026, Dconnex and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Hold and Release Note', {
	setup(frm) {
		frm.set_query('receipt_no', () => ({ filters: { docstatus: 1 } }));

		// Hold: occupied bins only. Release: held bins only.
		frm.set_query('bin', () => {
			if (frm.doc.action === 'Release') {
				return { filters: { on_hold: 1 } };
			}
			return { filters: { status: ['in', ['Occupied', 'Partially Occupied']] } };
		});
	},

	refresh(frm) {
		// bins come from Fetch Bins; rows can be removed but not typed in
		frm.get_field('bins').grid.cannot_add_rows = true;
		frm.refresh_field('bins');
	},

	action(frm) {
		frm.set_value('bin', null);
		frm.clear_table('bins');
		frm.refresh_field('bins');
	},

	fetch_bins(frm) {
		if (frm.doc.docstatus !== 0) return;
		frappe.call({
			method: 'fetch_bins',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Fetching bins...'),
			callback(r) {
				const res = r.message || {};
				const rows = res.rows || [];
				if ((res.skipped || []).length) {
					frappe.msgprint(__('Skipped (stock reserved on a Preparation Order): {0}', [res.skipped.join(', ')]));
				}
				frm.clear_table('bins');
				rows.forEach(d => frm.add_child('bins', d));
				frm.refresh_field('bins');
				if (!rows.length && !(res.skipped || []).length) {
					frappe.msgprint(__('No bins found for these filters (for {0}).', [frm.doc.action]));
				}
			}
		});
	}
});
