# Copyright (c) 2025, raion digital
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff
from calendar import month_name


def execute(filters=None):
    view_mode = (filters or {}).get("view_mode")

    if view_mode == "Detailed Invoice View":
        if not filters.get("sales_invoice"):
            frappe.msgprint(
                _("Please select a Sales Invoice for the Detailed View."),
                indicator="orange",
                title=_("Filter Required"),
            )
            return [], [], None, None, None
        columns = get_invoice_progress_columns()
        data = get_invoice_progress_data(filters)
        chart = get_invoice_progress_chart(data)
        return columns, data, None, chart, None

    elif view_mode == "Monthly Detailed View":
        if not filters.get("month") or not filters.get("year"):
            frappe.msgprint(
                _("Please select a Month and Year for the Detailed View."),
                indicator="orange",
                title=_("Filter Required"),
            )
            return [], [], None, None, None
        columns = get_monthly_details_columns()
        data = get_monthly_details_data(filters)
        return columns, data, None, None, None

    else:  # Summary View (default)
        is_yearly_view = date_diff(filters.get("to_date"), filters.get("from_date")) > 365
        columns = get_summary_columns(is_yearly_view)
        data, chart, report_summary = get_summary_data(filters, is_yearly_view)
        return columns, data, None, chart, report_summary


# -----------------------------
# Monthly Detailed View
# -----------------------------

def get_monthly_details_columns():
    return [
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
        {"label": _("Executed Value"), "fieldname": "executed_value", "fieldtype": "Currency", "width": 130},
        {"label": _("Execution %"), "fieldname": "execution_percentage", "fieldtype": "Percent", "width": 110},
        {"label": _("Cumulative %"), "fieldname": "cumulative_execution", "fieldtype": "Percent", "width": 110},
        {"label": _("Sales Person Comm %"), "fieldname": "sp_comm_pct", "fieldtype": "Percent", "width": 120},
        {"label": _("SP Commission"), "fieldname": "sp_commission", "fieldtype": "Currency", "width": 130},
        {"label": _("Shareholder Commission"), "fieldname": "shareholder_commission", "fieldtype": "Currency", "width": 150},
    ]


def get_monthly_details_data(filters):
    sql_filters = {
        "company": filters.get("company"),
        "month": int(filters.get("month")),
        "year": int(filters.get("year")),
    }

    rows = frappe.db.sql(
        """
        SELECT 
            mp.report_month AS date, 
            ese.sales_invoice, 
            si.customer, 
            ese.actual_executed_value AS executed_value,
            ese.execution_percentage,
            ese.cumulative_execution,
            COALESCE(ese.sales_person_commission, sp.commission_rate) AS sp_comm_pct,
            COALESCE(mp.total_commission_amount, 0) AS doc_shareholder_total
        FROM `tabMonthly Productivity` mp
        JOIN `tabExecution Schedule Entry` ese ON mp.name = ese.parent
        LEFT JOIN `tabSales Invoice` si ON ese.sales_invoice = si.name
        LEFT JOIN `tabSales Person` sp ON ese.sales_person = sp.name
        WHERE mp.docstatus = 1
          AND mp.company = %(company)s 
          AND MONTH(mp.report_month) = %(month)s 
          AND YEAR(mp.report_month) = %(year)s
        ORDER BY mp.report_month, ese.sales_invoice
        """,
        sql_filters,
        as_dict=1,
    )

    if not rows:
        return []

    total_executed = sum((r.executed_value or 0) for r in rows)

    # Allocate the document-level shareholder total proportionally by executed value
    for r in rows:
        exe = r.executed_value or 0
        sp_pct = float(r.sp_comm_pct or 0)
        r["sp_commission"] = exe * (sp_pct / 100.0)

        share = (exe / total_executed) if total_executed else 0
        # distribute mp.total_commission_amount proportionally
        r["shareholder_commission"] = (r.doc_shareholder_total or 0) * share

    return rows


# -----------------------------
# Invoice Progress View
# -----------------------------

def get_invoice_progress_columns():
    return [
        {"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 200},
        {"label": _("Execution % This Period"), "fieldname": "execution_percentage", "fieldtype": "Percent", "width": 200},
        {"label": _("Cumulative Execution %"), "fieldname": "cumulative_execution", "fieldtype": "Percent", "width": 200},
        {"label": _("Monthly Productivity Doc"), "fieldname": "monthly_productivity_doc", "fieldtype": "Link", "options": "Monthly Productivity", "width": 200},
    ]


def get_invoice_progress_data(filters):
    progress_entries = frappe.db.sql(
        """
        SELECT 
            mp.name AS monthly_productivity_doc,
            mp.report_month,
            ese.execution_percentage,
            ese.cumulative_execution
        FROM `tabExecution Schedule Entry` AS ese
        JOIN `tabMonthly Productivity` AS mp ON ese.parent = mp.name
        WHERE ese.sales_invoice = %(sales_invoice)s
          AND mp.docstatus = 1
        ORDER BY mp.report_month ASC
        """,
        filters,
        as_dict=1,
    )

    report_data = []
    for entry in progress_entries:
        year, month_num, _ = str(entry.report_month).split("-")
        formatted_month = f"{_(month_name[int(month_num)])} {year}"
        report_data.append(
            {
                "month": formatted_month,
                "execution_percentage": entry.execution_percentage,
                "cumulative_execution": entry.cumulative_execution,
                "monthly_productivity_doc": entry.monthly_productivity_doc,
            }
        )
    return report_data


def get_invoice_progress_chart(data):
    if not data:
        return None
    labels = [row["month"] for row in data]
    datasets = [
        {"name": _("Execution % This Period"), "values": [row["execution_percentage"] for row in data]},
        {"name": _("Cumulative Execution %"), "values": [row["cumulative_execution"] for row in data]},
    ]
    return {"data": {"labels": labels, "datasets": datasets}, "type": "bar", "height": 300, "title": _("Invoice Progress (%)")}


# -----------------------------
# Summary View
# -----------------------------

def get_summary_columns(is_yearly_view):
    period_label = _("Year") if is_yearly_view else _("Month")
    return [
        {"label": period_label, "fieldname": "period", "fieldtype": "Data", "width": 130},
        {"label": _("Executed Value"), "fieldname": "executed_value", "fieldtype": "Currency", "width": 140},
        {"label": _("Total Purchases"), "fieldname": "total_purchases", "fieldtype": "Currency", "width": 140},
        {"label": _("Other Expenses"), "fieldname": "other_expenses", "fieldtype": "Currency", "width": 140},
        {"label": _("Sales Person Commission"), "fieldname": "sp_commission", "fieldtype": "Currency", "width": 140},
        {"label": _("Shareholder Commission"), "fieldname": "shareholder_commission", "fieldtype": "Currency", "width": 170},
        {"label": _("Profit or Loss"), "fieldname": "profit_loss", "fieldtype": "Currency", "width": 150},
    ]


def get_summary_data(filters, is_yearly_view):
    date_format = "'%%Y'" if is_yearly_view else "'%%Y-%%m'"
    sql_filters = {
        "company": filters.get("company"),
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
    }

    # 1) Executed value + weighted SP% per period
    exec_and_sp_pct = frappe.db.sql(
        f"""
        SELECT
            DATE_FORMAT(mp.report_month, {date_format}) AS period_group,
            SUM(ese.actual_executed_value) AS total_executed_value,
            CASE WHEN SUM(ese.actual_executed_value) = 0 THEN 0
                 ELSE SUM(ese.actual_executed_value * COALESCE(ese.sales_person_commission, sp.commission_rate, 0))
                      / SUM(ese.actual_executed_value)
            END AS avg_sp_comm_pct
        FROM `tabMonthly Productivity` mp
        JOIN `tabExecution Schedule Entry` ese ON mp.name = ese.parent
        LEFT JOIN `tabSales Person` sp ON ese.sales_person = sp.name
        WHERE mp.docstatus = 1
          AND mp.company = %(company)s
          AND mp.report_month BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period_group
        """,
        sql_filters,
        as_dict=1,
    )

    # 2) Purchases per period
    purchases_data = frappe.db.sql(
        f"""
        SELECT DATE_FORMAT(pi.posting_date, {date_format}) AS period_group,
               SUM(pi.base_grand_total) AS total_purchases
        FROM `tabPurchase Invoice` pi
        WHERE pi.docstatus = 1
          AND pi.company = %(company)s
          AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period_group
        """,
        sql_filters,
        as_dict=1,
    )

    # 3) Other expenses per period
    other_expenses_data = frappe.db.sql(
        f"""
        SELECT DATE_FORMAT(je.posting_date, {date_format}) AS period_group,
               SUM(jea.debit_in_account_currency) AS total_other_expenses
        FROM `tabJournal Entry Account` jea
        JOIN `tabJournal Entry` je ON je.name = jea.parent
        WHERE je.docstatus = 1
          AND je.company = %(company)s
          AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
          AND LEFT(jea.account, 2) IN ('62', '63', '64', '65', '66', '67', '68', '69')
        GROUP BY period_group
        """,
        sql_filters,
        as_dict=1,
    )

    # 4) NEW: Sum parent-level shareholder commission amount per period
    shareholder_sums = frappe.db.sql(
        f"""
        SELECT DATE_FORMAT(mp.report_month, {date_format}) AS period_group,
               SUM(COALESCE(mp.total_commission_amount, 0)) AS sh_commission_sum
        FROM `tabMonthly Productivity` mp
        WHERE mp.docstatus = 1
          AND mp.company = %(company)s
          AND mp.report_month BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY period_group
        """,
        sql_filters,
        as_dict=1,
    )

    # Merge into period summary
    period_summary = {}
    for row in exec_and_sp_pct:
        period_summary[row.period_group] = frappe._dict(
            executed_value=row.total_executed_value or 0,
            avg_sp_comm_pct=float(row.avg_sp_comm_pct or 0),
            total_purchases=0,
            other_expenses=0,
            shareholder_commission=0.0,
        )

    for row in purchases_data:
        ps = period_summary.setdefault(
            row.period_group,
            frappe._dict(
                executed_value=0,
                avg_sp_comm_pct=0.0,
                total_purchases=0,
                other_expenses=0,
                shareholder_commission=0.0,
            ),
        )
        ps.total_purchases += row.total_purchases or 0

    for row in other_expenses_data:
        ps = period_summary.setdefault(
            row.period_group,
            frappe._dict(
                executed_value=0,
                avg_sp_comm_pct=0.0,
                total_purchases=0,
                other_expenses=0,
                shareholder_commission=0.0,
            ),
        )
        ps.other_expenses += row.total_other_expenses or 0

    for row in shareholder_sums:
        ps = period_summary.setdefault(
            row.period_group,
            frappe._dict(
                executed_value=0,
                avg_sp_comm_pct=0.0,
                total_purchases=0,
                other_expenses=0,
                shareholder_commission=0.0,
            ),
        )
        ps.shareholder_commission += row.sh_commission_sum or 0

    # Compose rows
    report_data = []
    for period, values in sorted(period_summary.items()):
        executed = values.executed_value or 0
        purchases = values.total_purchases or 0
        other_exp = values.other_expenses or 0
        base_profit = executed - purchases - other_exp

        sp_commission_amt = executed * ((values.avg_sp_comm_pct or 0) / 100.0)
        shareholder_commission_amt = values.shareholder_commission or 0
        final_profit = base_profit - shareholder_commission_amt - sp_commission_amt

        year, month_num = (period, "01") if is_yearly_view else period.split("-")
        formatted_period = year if is_yearly_view else f"{_(month_name[int(month_num)])} {year}"

        report_data.append(
            {
                "period": formatted_period,
                "executed_value": executed,
                "total_purchases": purchases,
                "other_expenses": other_exp,
                "sp_commission": sp_commission_amt,
                "shareholder_commission": shareholder_commission_amt,
                "profit_loss": final_profit,
            }
        )

    chart = get_chart_data(report_data)
    summary = get_report_summary(report_data)
    return report_data, chart, summary


def get_chart_data(data):
    if not data:
        return None
    labels = [row["period"] for row in data if "Total" not in row.get("period", "")]
    datasets = [
        {"name": _("Executed Value"), "values": [r["executed_value"] for r in data if "Total" not in r.get("period", "")]},
        {"name": _("Profit or Loss"), "values": [r["profit_loss"] for r in data if "Total" not in r.get("period", "")]},
        {"name": _("Sales Person Commission"), "values": [r["sp_commission"] for r in data if "Total" not in r.get("period", "")]},
        {"name": _("Shareholder Commission"), "values": [r["shareholder_commission"] for r in data if "Total" not in r.get("period", "")]},
    ]
    return {"data": {"labels": labels, "datasets": datasets}, "type": "bar", "height": 300}


def get_report_summary(data):
    if not data:
        return None
    rows_to_sum = [row for row in data if "Total" not in row.get("period", "")]
    total_executed = sum(r.get("executed_value", 0) for r in rows_to_sum)
    total_sp_comm = sum(r.get("sp_commission", 0) for r in rows_to_sum)
    total_sh_comm = sum(r.get("shareholder_commission", 0) for r in rows_to_sum)
    total_profit_after_commission = sum(r.get("profit_loss", 0) for r in rows_to_sum)

    return [
        {"value": total_executed, "label": _("Total Executed Value"), "datatype": "Currency", "indicator": "Green" if total_executed >= 0 else "Red"},
        {"value": total_sp_comm, "label": _("Total Sales Person Commission"), "datatype": "Currency", "indicator": "Green" if total_sp_comm >= 0 else "Red"},
        {"value": total_sh_comm, "label": _("Total Shareholder Commission"), "datatype": "Currency", "indicator": "Green" if total_sh_comm >= 0 else "Red"},
        {"value": total_profit_after_commission, "label": _("Total Profit / Loss"), "datatype": "Currency", "indicator": "Green" if total_profit_after_commission >= 0 else "Red"},
    ]
