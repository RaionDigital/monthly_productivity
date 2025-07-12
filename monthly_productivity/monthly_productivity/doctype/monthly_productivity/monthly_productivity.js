// Copyright (c) 2025, raion digital and contributors
// For license information, please see license.txt
// --- Monthly Productivity Form Events
frappe.ui.form.on('Monthly Productivity', {
    sales_invoice(frm) {
        const inv = frm.doc.sales_invoice;
        if (!inv) return;

        frappe.db.get_value('Sales Invoice', inv, 'grand_total', r => {
            const total = r.grand_total || 0;

            (frm.doc.execution_schedule_entries || []).forEach(row => {
                frappe.model.set_value(row.doctype, row.name, 'invoice_total', total);
                const actual = total * (row.execution_percentage || 0) / 100;
                frappe.model.set_value(row.doctype, row.name, 'actual_executed_value', actual);
            });
        });
    },

    execution_schedule_entries_add(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const inv = frm.doc.sales_invoice;
        if (!inv) return;

        frappe.db.get_value('Sales Invoice', inv, 'grand_total', r => {
            frappe.model.set_value(cdt, cdn, 'sales_invoice', inv);
            const total = r.grand_total || 0;
            frappe.model.set_value(cdt, cdn, 'invoice_total', total);
            const actual = total * (row.execution_percentage || 0) / 100;
            frappe.model.set_value(cdt, cdn, 'actual_executed_value', actual);
        });
    }
});

// --- Execution Schedule Entry Child Table
frappe.ui.form.on('Execution Schedule Entry', {
    execution_percentage(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const total = row.invoice_total || 0;

        // --- Actual Executed Value (Preserved Logic)
        const actual = total * (row.execution_percentage || 0) / 100;
        frappe.model.set_value(cdt, cdn, 'actual_executed_value', actual);

        // --- Cumulative Execution (NEW)
        if (!row.sales_invoice) return;

        frappe.db.get_list('Monthly Productivity', {
            filters: {
                docstatus: 1,
                name: ['!=', frm.doc.name]
            },
            fields: ['name']
        }).then(submittedDocs => {
            const submittedNames = submittedDocs.map(doc => doc.name);

            frappe.db.get_list('Execution Schedule Entry', {
                filters: {
                    parent: ['in', submittedNames],
                    sales_invoice: row.sales_invoice
                },
                fields: ['execution_percentage']
            }).then(previousRows => {
                const previousTotal = previousRows.reduce(
                    (sum, r) => sum + (r.execution_percentage || 0), 0
                );

                const current = row.execution_percentage || 0;
                const cumulative = previousTotal + current;

                frappe.model.set_value(cdt, cdn, 'cumulative_execution', cumulative);
            });
        });
    }
});

