// Copyright (c) 2025, raion digital and contributors
// For license information, please see license.txt

// Utilities
function mp_sum_productivity_actual(frm) {
  let base = 0;
  (frm.doc.productivity || []).forEach(r => {
    base += flt(r.actual_executed_value || 0);
  });
  return flt(base);
}

function mp_recompute_commissions(frm) {
  const base = mp_sum_productivity_actual(frm);
  let total_pct = 0;
  let total_amt = 0;

  (frm.doc.commission_breakdown || []).forEach(r => {
    const pct = flt(r.commission_percentage || 0);
    const amt = Math.round((base * pct / 100) * 100) / 100;
    frappe.model.set_value(r.doctype, r.name, 'commission_amount', amt);
    total_pct += pct;
    total_amt += amt;
  });

  frm.set_value('total_commission_percentage', flt(total_pct));
  frm.set_value('total_commission_amount', flt(total_amt));
}

frappe.ui.form.on('Monthly Productivity', {
  onload(frm) {
    // Limit selectable Sales Invoices in the child grid to submitted only
    frm.set_query('sales_invoice', 'productivity', () => ({
      filters: { docstatus: 1 }
    }));
  },

  // When a productivity row is added, just ensure numbers recalc once user fills fields
  productivity_add(frm, cdt, cdn) {
    // nothing to prefill; calculations happen on field change
  }
});

// -------------------------
// Execution Schedule Entry
// -------------------------
frappe.ui.form.on('Execution Schedule Entry', {
  // When the Sales Invoice is chosen in a child row:
  sales_invoice(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.sales_invoice) { return; }

    frappe.db.get_value('Sales Invoice', row.sales_invoice, 'grand_total')
      .then(r => {
        const total = (r && r.message && r.message.grand_total) || 0;
        frappe.model.set_value(cdt, cdn, 'invoice_total', total);

        const actual = total * (flt(row.execution_percentage || 0) / 100.0);
        frappe.model.set_value(cdt, cdn, 'actual_executed_value', actual);

        // Commissions are based on sum of actuals; update totals
        mp_recompute_commissions(frm);
      });
  },

  // When execution % changes: compute actual value and validate cumulative <= 100%
  execution_percentage(frm, cdt, cdn) {
    const currentRow = locals[cdt][cdn];
    const totalInvoiceValue = flt(currentRow.invoice_total || 0);
    const currentPct = flt(currentRow.execution_percentage || 0);

    // Update actual_executed_value
    const actualValue = totalInvoiceValue * (currentPct / 100.0);
    frappe.model.set_value(cdt, cdn, 'actual_executed_value', actualValue);

    if (!currentRow.sales_invoice) {
      // No invoice yet; show only the in-row value as cumulative for now
      frappe.model.set_value(cdt, cdn, 'cumulative_execution', currentPct);
      mp_recompute_commissions(frm);
      return;
    }

    // Sum percentages for same invoice within THIS doc (excluding current row)
    let pct_in_doc = 0;
    (frm.doc.productivity || []).forEach(row => {
      if (row.name !== currentRow.name && row.sales_invoice === currentRow.sales_invoice) {
        pct_in_doc += flt(row.execution_percentage || 0);
      }
    });

    // Fetch sum from submitted docs (excluding this doc)
    frappe.call({
      method: 'monthly_productivity.monthly_productivity.doctype.monthly_productivity.monthly_productivity.get_previous_execution_total',
      args: {
        sales_invoice: currentRow.sales_invoice,
        current_doc_name: frm.doc.name
      },
      callback: function (r) {
        const previousDocsTotal = flt(r.message || 0);
        const proposed_total = previousDocsTotal + pct_in_doc + currentPct;

        if (proposed_total > 100) {
          frappe.msgprint({
            title: __('Validation Error'),
            indicator: 'red',
            message: __(
              'Total execution for Sales Invoice {0} cannot exceed 100%. The proposed total is {1}%.',
              [`<b>${currentRow.sales_invoice}</b>`, `<b>${proposed_total}</b>`]
            ),
          });
          // Reset invalid entry
          frappe.model.set_value(cdt, cdn, 'execution_percentage', 0);
          frappe.model.set_value(cdt, cdn, 'actual_executed_value', 0);
          frappe.model.set_value(cdt, cdn, 'cumulative_execution',
            previousDocsTotal + pct_in_doc);
        } else {
          frappe.model.set_value(cdt, cdn, 'cumulative_execution', proposed_total);
        }

        // Commissions depend on sum of actuals; update totals
        mp_recompute_commissions(frm);
      }
    });
  },

  // If invoice_total ever changes manually, recompute actual + commissions
  invoice_total(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const actual = flt(row.invoice_total || 0) * (flt(row.execution_percentage || 0) / 100.0);
    frappe.model.set_value(cdt, cdn, 'actual_executed_value', actual);
    mp_recompute_commissions(frm);
  },

  // If actual is edited directly, still refresh commissions
  actual_executed_value(frm) {
    mp_recompute_commissions(frm);
  }
});

// ---------------------------------------------
// Monthly Productivity Commission Row (child)
// ---------------------------------------------
frappe.ui.form.on('Monthly Productivity Commission Row', {
  // When a shareholder is picked, auto-fill commission_percentage from Shareholder
  shareholder(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (!row.shareholder) {
      // If cleared, also clear percentage & amount
      frappe.model.set_value(cdt, cdn, 'commission_percentage', 0);
      frappe.model.set_value(cdt, cdn, 'commission_amount', 0);
      mp_recompute_commissions(frm);
      return;
    }

    frappe.db.get_value('Shareholder', row.shareholder, 'commission_percentage')
      .then(r => {
        const pct = (r && r.message && r.message.commission_percentage) || 0;
        frappe.model.set_value(cdt, cdn, 'commission_percentage', pct);
        mp_recompute_commissions(frm);
      });
  },

  // If user edits percentage manually, recompute amounts & totals
  commission_percentage(frm) {
    mp_recompute_commissions(frm);
  },

  // Keep totals in sync when rows are added/removed
  commission_breakdown_add(frm) {
    mp_recompute_commissions(frm);
  },
  commission_breakdown_remove(frm) {
    mp_recompute_commissions(frm);
  }
});
