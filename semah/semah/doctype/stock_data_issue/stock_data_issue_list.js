const SDI_API = "semah.semah.doctype.stock_data_issue.stock_data_issue";

const SDI_CHECKS = [
	"Location vs Ledger Qty Mismatch",
	"Negative Stock",
	"Invalid Bin Location",
	"Batch Issues",
	"Wrong UOM Conversion",
	"Reserved Qty Exceeds Stored",
	"Bin Outside Item Warehouse",
	"Duplicate Location Rows",
	"Bin Status Mismatch",
	"Disabled Item With Stock",
	"Expired Stock",
	"Possible Duplicate Items",
];

frappe.listview_settings["Stock Data Issue"] = {
	add_fields: ["status", "severity", "fix_action"],
	hide_name_column: false,

	get_indicator(doc) {
		if (doc.status === "Fixed") return [__("Fixed"), "green", "status,=,Fixed"];
		if (doc.status === "Ignored") return [__("Ignored"), "gray", "status,=,Ignored"];
		const color = { Critical: "red", Warning: "orange", Info: "blue" }[doc.severity];
		return [__("Open"), color, "status,=,Open"];
	},

	onload(listview) {
		listview.page.add_inner_button(__("Scan Now"), () => scan_dialog(listview));
		listview.page.add_inner_button(__("Fix Issues"), () => fix_dialog(listview)).addClass("btn-primary");
		listview.page.add_actions_menu_item(__("Ignore Selected"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("Select records first"));
			frappe.prompt(
				{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes"), reqd: 1 },
				(v) =>
					frappe.call({
						method: `${SDI_API}.set_status`,
						args: { names, status: "Ignored", notes: v.notes },
						callback: () => listview.refresh(),
					}),
				__("Ignore {0} Issue(s)", [names.length])
			);
		});
	},
};

function scan_dialog(listview) {
	const d = new frappe.ui.Dialog({
		title: __("Scan Stock Data"),
		fields: [
			{ fieldname: "from_date", fieldtype: "Date", label: __("From Date"), default: "2026-02-01", reqd: 1 },
			{ fieldname: "include_info", fieldtype: "Check", label: __("Include Info Checks (expired stock, duplicate items)") },
		],
		primary_action_label: __("Scan"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: `${SDI_API}.scan`,
				args: values,
				freeze: true,
				freeze_message: __("Scanning stock data..."),
				callback: (r) => {
					const m = r.message;
					frappe.msgprint(
						__("Found {0} issue(s): {1} new, {2} reopened, {3} auto-closed as no longer detected.", [
							m.found, m.created, m.reopened, m.auto_closed,
						])
					);
					listview.refresh();
				},
			});
		},
	});
	d.show();
}

function fix_dialog(listview) {
	let issues = [];
	const d = new frappe.ui.Dialog({
		title: __("Fix Issues"),
		size: "extra-large",
		fields: [
			{
				fieldname: "check",
				fieldtype: "Select",
				label: __("Issue Type"),
				options: ["", ...SDI_CHECKS],
				reqd: 1,
				onchange: () => load_issues(),
			},
			{ fieldname: "fix_info", fieldtype: "HTML" },
			{ fieldname: "issues_html", fieldtype: "HTML" },
		],
		primary_action_label: __("Fix Selected"),
		primary_action(values) {
			const names = d.$wrapper.find(".sdi-row:checked").map((_, el) => el.value).get();
			if (!names.length) return frappe.msgprint(__("Select at least one record"));
			frappe.confirm(__("Apply fix to {0} record(s) of <b>{1}</b>?", [names.length, values.check]), () =>
				frappe.call({
					method: `${SDI_API}.apply_fixes`,
					args: { names },
					freeze: true,
					freeze_message: __("Applying fixes..."),
					callback: (r) => {
						const m = r.message;
						let msg = __("Fixed {0} record(s).", [m.fixed]);
						if (m.failed.length) msg += `<br><br><b>${__("Failed")}:</b><br>${m.failed.map(frappe.utils.escape_html).join("<br>")}`;
						frappe.msgprint(msg);
						load_issues();
						listview.refresh();
					},
				})
			);
		},
	});

	function load_issues() {
		const check = d.get_value("check");
		d.fields_dict.issues_html.$wrapper.empty();
		d.fields_dict.fix_info.$wrapper.empty();
		if (!check) return;
		frappe.db
			.get_list("Stock Data Issue", {
				filters: { check, status: "Open" },
				fields: ["name", "item_code", "item_name", "customer", "warehouse", "bin_location", "reference_name",
					"ledger_qty", "location_qty", "difference", "details", "fix_action"],
				limit: 1000,
				order_by: "item_code asc",
			})
			.then((rows) => {
				issues = rows;
				render(check);
			});
	}

	function render(check) {
		const fixable = issues.filter((i) => i.fix_action);
		const manual = issues.length - fixable.length;
		const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
		const fmt = (v) => (v == null ? "" : format_number(v, null, 2));

		d.fields_dict.fix_info.$wrapper.html(
			`<div class="text-muted small mb-2">${__("{0} open record(s) for {1}: {2} with automatic fix, {3} need manual correction.", [
				issues.length, esc(check), fixable.length, manual,
			])}</div>`
		);
		if (!issues.length) {
			d.fields_dict.issues_html.$wrapper.html(`<div class="text-muted">${__("No open issues of this type.")}</div>`);
			return;
		}

		const body = issues
			.map(
				(i) => `<tr>
				<td><input type="checkbox" class="sdi-row" value="${esc(i.name)}" ${i.fix_action ? "" : "disabled"}></td>
				<td><a href="/app/stock-data-issue/${esc(i.name)}" target="_blank">${esc(i.name)}</a></td>
				<td>${esc(i.item_code)}<div class="text-muted small">${esc(i.item_name)}</div></td>
				<td>${esc(i.warehouse)}</td>
				<td>${esc(i.bin_location)}</td>
				<td>${esc(i.reference_name)}</td>
				<td class="text-right">${fmt(i.ledger_qty)}</td>
				<td class="text-right">${fmt(i.location_qty)}</td>
				<td class="small">${esc(i.details)}</td>
				<td class="small">${i.fix_action ? esc(i.fix_action) : `<span class="text-muted">${__("Manual")}</span>`}</td>
			</tr>`
			)
			.join("");

		d.fields_dict.issues_html.$wrapper.html(`
			<div style="max-height: 55vh; overflow: auto;">
			<table class="table table-bordered table-sm small">
				<thead><tr>
					<th><input type="checkbox" class="sdi-all" title="${__("Select all fixable")}" ${fixable.length ? "" : "disabled"}></th>
					<th>${__("Issue")}</th><th>${__("Item")}</th><th>${__("Warehouse")}</th><th>${__("Bin")}</th>
					<th>${__("Reference")}</th><th>${__("Ledger Qty")}</th><th>${__("Location Qty")}</th>
					<th>${__("Details")}</th><th>${__("Fix")}</th>
				</tr></thead>
				<tbody>${body}</tbody>
			</table></div>`);

		d.$wrapper.find(".sdi-all").on("change", (e) =>
			d.$wrapper.find(".sdi-row:not(:disabled)").prop("checked", e.target.checked)
		);
	}

	d.show();
	const checked = listview.get_checked_items();
	if (checked.length && checked.every((c) => c.check === checked[0].check)) {
		d.set_value("check", checked[0].check);
	}
}
