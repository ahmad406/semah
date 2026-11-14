frappe.query_reports["Stock Data Integrity Check"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: "2026-02-01",
			reqd: 1,
		},
		{
			fieldname: "check",
			label: __("Check"),
			fieldtype: "Select",
			options: [
				"",
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
			],
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "include_info",
			label: __("Include Info Checks"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "severity" && data) {
			const color = { Critical: "red", Warning: "orange", Info: "blue" }[data.severity];
			value = `<span class="indicator-pill ${color}">${value}</span>`;
		}
		return value;
	},
};
