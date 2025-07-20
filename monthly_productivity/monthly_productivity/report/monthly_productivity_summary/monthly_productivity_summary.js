// Copyright (c) 2025, raion digital and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Monthly Productivity Summary"] = {
	filters: [
		// --- NEW: View Mode selector ---
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: ["Summary View", "Detailed Invoice View"],
			default: "Summary View",
			reqd: 1,
			// This 'on_change' function triggers when the user selects a mode.
			on_change: function () {
				let view_mode = frappe.query_report.get_filter_value("view_mode");
				let sales_invoice_filter = frappe.query_report.get_filter("sales_invoice");

				// Show or hide the Sales Invoice filter based on the selected mode.
				if (view_mode === "Detailed Invoice View") {
					sales_invoice_filter.df.hidden = 0;
					sales_invoice_filter.df.reqd = 1; // Make it required
				} else {
					sales_invoice_filter.df.hidden = 1;
					sales_invoice_filter.df.reqd = 0; // Make it not required
					// Clear the value when hiding to avoid confusion
					frappe.query_report.set_filter_value("sales_invoice", "");
				}
				// Refresh the filter display to apply changes.
				sales_invoice_filter.refresh();
			},
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		// Sales Invoice filter is now initially hidden.
		{
			fieldname: "sales_invoice",
			label: __("Sales Invoice"),
			fieldtype: "Link",
			options: "Sales Invoice",
			hidden: 1, // Start as hidden by default.
			get_query: function () {
				var company = frappe.query_report.get_filter_value("company");
				return {
					doctype: "Sales Invoice",
					filters: {
						company: company,
						docstatus: 1,
					},
				};
			},
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (row && data && data.period && data.period.includes("Total")) {
			return `<strong>${value}</strong>`;
		}
		return value;
	},
};
