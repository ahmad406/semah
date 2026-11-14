const STOCK_DATA_ISSUE_API = "semah.semah.doctype.stock_data_issue.stock_data_issue";

frappe.ui.form.on("Stock Data Issue", {
	refresh(frm) {
		frm.disable_save();
		if (frm.doc.status === "Open" && frm.doc.fix_action) {
			frm.add_custom_button(__("Apply Fix: {0}", [frm.doc.fix_action]), () => {
				frappe.confirm(
					__("Apply <b>{0}</b> for this issue?", [frm.doc.fix_action]),
					() =>
						frappe.call({
							method: `${STOCK_DATA_ISSUE_API}.apply_fix`,
							args: { name: frm.doc.name },
							freeze: true,
							callback: (r) => {
								frappe.show_alert({ message: r.message, indicator: "green" });
								frm.reload_doc();
							},
						})
				);
			}).addClass("btn-primary");
		}
		if (frm.doc.status === "Open") {
			frm.add_custom_button(__("Ignore"), () => set_issue_status([frm.doc.name], "Ignored", () => frm.reload_doc()));
		} else {
			frm.add_custom_button(__("Reopen"), () => set_issue_status([frm.doc.name], "Open", () => frm.reload_doc()));
		}
		if (!frm.doc.fix_action && frm.doc.status === "Open") {
			frm.dashboard.set_headline(__("No automatic fix for this check. Correct it manually, then mark it Ignored or re-scan."));
		}
	},
});

function set_issue_status(names, status, callback) {
	frappe.prompt(
		{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes"), reqd: status === "Ignored" },
		(values) =>
			frappe.call({
				method: `${STOCK_DATA_ISSUE_API}.set_status`,
				args: { names, status, notes: values.notes },
				callback,
			}),
		status === "Ignored" ? __("Ignore Issue") : __("Reopen Issue")
	);
}
