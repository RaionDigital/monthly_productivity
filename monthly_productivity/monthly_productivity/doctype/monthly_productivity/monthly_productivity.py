# Copyright (c) 2025, raion digital and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MonthlyProductivity(Document):
    def validate(self):
        """
        - Validate productivity rows (your existing logic kept).
        - Compute shareholder commission amounts from the commission_breakdown table.
        """
        self._validate_and_compute_productivity_rows()
        self._compute_shareholder_commissions()

    # -------------------
    # COMMISSIONS
    # -------------------
    def _commission_base_amount(self) -> float:
        """Base amount for commissions: sum of actual_executed_value across productivity rows."""
        total = 0.0
        for row in (self.get("productivity") or []):
            total += flt(getattr(row, "actual_executed_value", 0))
        return flt(total, 2)

    def _compute_shareholder_commissions(self):
        """Compute each row's commission_amount, plus parent totals."""
        rows = self.get("commission_breakdown") or []
        if not rows:
            self.total_commission_percentage = 0.0
            self.total_commission_amount = 0.0
            return

        base = self._commission_base_amount()
        total_pct = 0.0
        total_amt = 0.0

        for r in rows:
            # Auto-fill % server-side if not set (in case client fetch didn't run)
            if not flt(getattr(r, "commission_percentage", 0)) and getattr(r, "shareholder", None):
                spct = frappe.db.get_value("Shareholder", r.shareholder, "commission_percentage") or 0
                r.commission_percentage = flt(spct)

            pct = flt(getattr(r, "commission_percentage", 0))
            amt = round(base * pct / 100.0, 2)
            r.commission_amount = amt
            total_pct += pct
            total_amt += amt

        self.total_commission_percentage = flt(total_pct, 2)
        self.total_commission_amount = flt(total_amt, 2)

    # -------------------
    # EXISTING PRODUCTIVITY LOGIC (unchanged)
    # -------------------
    def _validate_and_compute_productivity_rows(self):
        rows = list(getattr(self, "productivity", []) or [])
        if not rows:
            return

        start_totals = {}
        for row in rows:
            inv = (getattr(row, "sales_invoice", "") or "").strip()
            if not inv:
                continue
            if inv not in start_totals:
                start_totals[inv] = flt(get_previous_execution_total(inv, self.name))

        in_doc_running = dict(start_totals)

        for row in rows:
            inv = (getattr(row, "sales_invoice", "") or "").strip()
            if not inv:
                self._ensure_sales_person_commission(row)
                continue

            self._ensure_sales_person_commission(row)

            current_exec = flt(getattr(row, "execution_percentage", 0))
            if current_exec < 0:
                frappe.throw(
                    _("Execution Percentage for Sales Invoice {0} cannot be negative.")
                    .format(frappe.bold(inv)),
                    title=_("Validation Error"),
                )

            posted_so_far = flt(start_totals.get(inv, 0.0))
            prior_in_doc = flt(in_doc_running.get(inv, posted_so_far)) - posted_so_far

            row.cumulative_execution = flt(posted_so_far + prior_in_doc, 2)

            proposed_total = posted_so_far + prior_in_doc + current_exec
            if proposed_total > 100.0:
                frappe.throw(
                    _(
                        "Total execution for Sales Invoice {0} cannot exceed 100%. "
                        "The proposed total is {1:.0f}%."
                    ).format(frappe.bold(inv), proposed_total),
                    title=_("Validation Error"),
                )

            total_after_row = posted_so_far + prior_in_doc + current_exec
            row.delivery_status = delivery_status_from_cumulative(total_after_row)

            if not flt(getattr(row, "actual_executed_value", 0)):
                inv_total = flt(getattr(row, "invoice_total", 0))
                row.actual_executed_value = flt(inv_total * (current_exec / 100.0), 2)

            in_doc_running[inv] = total_after_row

    def _ensure_sales_person_commission(self, row):
        sp = getattr(row, "sales_person", None)
        if not sp:
            frappe.throw(
                _("Row {0}: Sales Person is mandatory.").format(row.idx),
                title=_("Validation Error"),
            )

        if flt(getattr(row, "sales_person_commission", 0)) > 0:
            return

        rate = frappe.db.get_value("Sales Person", sp, "commission_rate")
        if rate is None:
            frappe.throw(
                _(
                    "Row {0}: Sales Person {1} has no commission rate. "
                    "Set 'Commission Rate' on the Sales Person record or add a 'commission_rate' field."
                ).format(row.idx, frappe.bold(sp)),
                title=_("Missing Commission Rate"),
            )

        row.sales_person_commission = flt(rate)


def delivery_status_from_cumulative(cum: float) -> str:
    if round(flt(cum), 2) >= 100.00:
        return "Delivered"
    if round(flt(cum), 2) <= 0.00:
        return "Not Started Yet"
    return "Not Delivered"


@frappe.whitelist()
def get_previous_execution_total(sales_invoice, current_doc_name):
    if not sales_invoice:
        return 0

    total_percentage = frappe.db.sql(
        """
        SELECT COALESCE(SUM(child.execution_percentage), 0)
        FROM `tabExecution Schedule Entry` AS child
        JOIN `tabMonthly Productivity` AS parent ON child.parent = parent.name
        WHERE parent.name != %(current_doc_name)s
          AND parent.docstatus = 1
          AND child.sales_invoice = %(sales_invoice)s
        """,
        {"current_doc_name": current_doc_name, "sales_invoice": sales_invoice},
    )
    return flt(total_percentage[0][0]) if total_percentage else 0
