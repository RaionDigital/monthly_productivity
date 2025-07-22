// Copyright (c) 2025, raion digital and contributors
// For license information, please see license.txt

// --- Monthly Productivity Form Events ---
frappe.ui.form.on("Monthly Productivity", {
	/**
	 * This onload event sets the filter for the sales_invoice field.
	 * It ensures only submitted documents can be selected.
	 */
	onload: function (frm) {
		// Replace 'productivity' with your child table's fieldname if it's different.
		// Replace 'sales_invoice' with your link field's fieldname if it's different.
		frm.set_query("sales_invoice", "productivity", function (doc, cdt, cdn) {
			return {
				filters: {
					// docstatus: 1 === Submitted
					docstatus: 1,
				},
			};
		});
	},

	sales_invoice(frm) {
		const inv = frm.doc.sales_invoice;
		if (!inv) return;

		frappe.db.get_value("Sales Invoice", inv, "grand_total", (r) => {
			const total = r.grand_total || 0;

			(frm.doc.productivity || []).forEach((row) => {
				frappe.model.set_value(row.doctype, row.name, "invoice_total", total);
				const actual = (total * (row.execution_percentage || 0)) / 100;
				frappe.model.set_value(row.doctype, row.name, "actual_executed_value", actual);
			});
		});
	},

	execution_schedule_entries_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const inv = frm.doc.sales_invoice;
		if (!inv) return;

		frappe.db.get_value("Sales Invoice", inv, "grand_total", (r) => {
			frappe.model.set_value(cdt, cdn, "sales_invoice", inv);
			const total = r.grand_total || 0;
			frappe.model.set_value(cdt, cdn, "invoice_total", total);
			const actual = (total * (row.execution_percentage || 0)) / 100;
			frappe.model.set_value(cdt, cdn, "actual_executed_value", actual);
		});
	},
});

// --- Execution Schedule Entry Child Table ---
// NOTE: I noticed your child table doctype is 'Execution Schedule Entry' but the field
// in the parent seems to be 'productivity'. I've used 'productivity' in the filter query
// above as that seems more likely to be the fieldname. Please double-check this.
frappe.ui.form.on("Execution Schedule Entry", {
	execution_percentage(frm, cdt, cdn) {
		const currentRow = locals[cdt][cdn];
		const totalInvoiceValue = currentRow.invoice_total || 0;

		const actualValue = totalInvoiceValue * (flt(currentRow.execution_percentage) / 100);
		frappe.model.set_value(cdt, cdn, "actual_executed_value", actualValue);

		if (!currentRow.sales_invoice) {
			frappe.model.set_value(
				cdt,
				cdn,
				"cumulative_execution",
				currentRow.execution_percentage || 0
			);
			return;
		}

		let percentageInCurrentDoc = 0;
		frm.doc.productivity.forEach((row) => {
			if (row.name !== currentRow.name && row.sales_invoice === currentRow.sales_invoice) {
				percentageInCurrentDoc += flt(row.execution_percentage);
			}
		});

		frappe.call({
			method: "monthly_productivity.monthly_productivity.doctype.monthly_productivity.monthly_productivity.get_previous_execution_total",
			args: {
				sales_invoice: currentRow.sales_invoice,
				current_doc_name: frm.doc.name,
			},
			callback: function (r) {
				const previousDocsTotal = flt(r.message);
				const currentPercentage = flt(currentRow.execution_percentage);
				const cumulativeTotal =
					previousDocsTotal + percentageInCurrentDoc + currentPercentage;

				// --- total excution % <= 100 ---
				if (cumulativeTotal > 100) {
					frappe.msgprint({
						title: __("Validation Error"),
						indicator: "red",
						message: __(
							"Total execution for Sales Invoice {0} cannot exceed 100%. The proposed total is {1}%.",
							[`<b>${currentRow.sales_invoice}</b>`, `<b>${cumulativeTotal}</b>`]
						),
					});
					// Clear the invalid value to force the user to correct it.
					frappe.model.set_value(cdt, cdn, "execution_percentage", 0);
				}

				frappe.model.set_value(cdt, cdn, "cumulative_execution", cumulativeTotal);
			},
		});
	},
});
