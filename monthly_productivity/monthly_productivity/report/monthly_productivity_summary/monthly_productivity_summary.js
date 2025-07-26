// Copyright (c) 2025, raion digital and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Monthly Productivity Summary"] = {
	filters: [
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: ["Summary View", "Monthly Detailed View", "Detailed Invoice View"],
			default: "Summary View",
			reqd: 1,
			on_change: function () {
				const view_mode = frappe.query_report.get_filter_value("view_mode");

				const set_filter_visibility = (fieldname, hidden, reqd) => {
					const filter = frappe.query_report.get_filter(fieldname);
					filter.df.hidden = hidden;
					filter.df.reqd = reqd;
					filter.refresh();
				};

				if (view_mode === "Monthly Detailed View") {
					set_filter_visibility("from_date", 1, 0);
					set_filter_visibility("to_date", 1, 0);
					set_filter_visibility("sales_invoice", 1, 0);
					set_filter_visibility("month", 0, 1);
					set_filter_visibility("year", 0, 1);
				} else if (view_mode === "Detailed Invoice View") {
					set_filter_visibility("from_date", 0, 1);
					set_filter_visibility("to_date", 0, 1);
					set_filter_visibility("sales_invoice", 0, 1);
					set_filter_visibility("month", 1, 0);
					set_filter_visibility("year", 1, 0);
				} else {
					// Summary View
					set_filter_visibility("from_date", 0, 1);
					set_filter_visibility("to_date", 0, 1);
					set_filter_visibility("sales_invoice", 1, 0);
					set_filter_visibility("month", 1, 0);
					set_filter_visibility("year", 1, 0);
				}

				frappe.query_report.refresh();
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
		// --- NEW: Month and Year filters ---
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				{ value: 1, label: __("January") },
				{ value: 2, label: __("February") },
				{ value: 3, label: __("March") },
				{ value: 4, label: __("April") },
				{ value: 5, label: __("May") },
				{ value: 6, label: __("June") },
				{ value: 7, label: __("July") },
				{ value: 8, label: __("August") },
				{ value: 9, label: __("September") },
				{ value: 10, label: __("October") },
				{ value: 11, label: __("November") },
				{ value: 12, label: __("December") },
			],
			default: new Date().getMonth() + 1,
			hidden: 1,
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			hidden: 1,
		},
		{
			fieldname: "sales_invoice",
			label: __("Sales Invoice"),
			fieldtype: "Link",
			options: "Sales Invoice",
			hidden: 1,
			get_query: function () {
				var company = frappe.query_report.get_filter_value("company");
				return { doctype: "Sales Invoice", filters: { company: company, docstatus: 1 } };
			},
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		let formatted_value = default_formatter(value, row, column, data);
		if (data) {
			const isTotalRow =
				(data.period && data.period.includes("Total")) ||
				(data.sales_invoice && data.sales_invoice.includes("Total"));
			if (isTotalRow) {
				if (column.fieldname === "sales_invoice" || column.fieldname === "period") {
					return `<strong>Total</strong>`;
				}
				return `<strong>${formatted_value}</strong>`;
			}
		}
		return formatted_value;
	},
};
