# Copyright (c) 2025, raion digital and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, date_diff
from calendar import month_name

def execute(filters=None):
	# Logic to switch between views remains the same
	if filters.get("view_mode") == "Detailed Invoice View":
		if not filters.get("sales_invoice"):
			frappe.msgprint(_("Please select a Sales Invoice for the Detailed View."), indicator='orange', title=_('Filter Required'))
			return [], [], None, None, None

		columns = get_invoice_progress_columns()
		data = get_invoice_progress_data(filters)
		chart = get_invoice_progress_chart(data)
		return columns, data, None, chart, None
	
	else:
		is_yearly_view = date_diff(filters.get("to_date"), filters.get("from_date")) > 365
		columns = get_summary_columns(is_yearly_view)
		data, chart, report_summary = get_summary_data(filters, is_yearly_view)
		return columns, data, None, chart, report_summary

# --- Functions for Invoice Progress (Detailed View) - UNCHANGED ---

def get_invoice_progress_columns():
	return [
		{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 200},
		{"label": _("Execution % This Period"), "fieldname": "execution_percentage", "fieldtype": "Percent", "width": 200},
		{"label": _("Cumulative Execution %"), "fieldname": "cumulative_execution", "fieldtype": "Percent", "width": 200},
		{"label": _("Monthly Productivity Doc"), "fieldname": "monthly_productivity_doc", "fieldtype": "Link", "options": "Monthly Productivity", "width": 200},
	]

def get_invoice_progress_data(filters):
	progress_entries = frappe.db.sql("""
		SELECT mp.name as monthly_productivity_doc, mp.report_month, ese.execution_percentage, ese.cumulative_execution
		FROM `tabExecution Schedule Entry` as ese JOIN `tabMonthly Productivity` as mp ON ese.parent = mp.name
		WHERE ese.sales_invoice = %(sales_invoice)s AND mp.docstatus = 1 ORDER BY mp.report_month ASC
	""", filters, as_dict=1)
	report_data = []
	for entry in progress_entries:
		year, month_num, day = str(entry.report_month).split('-')
		formatted_month = f"{_(month_name[int(month_num)])} {year}"
		report_data.append({"month": formatted_month, "execution_percentage": entry.execution_percentage, "cumulative_execution": entry.cumulative_execution, "monthly_productivity_doc": entry.monthly_productivity_doc})
	return report_data

def get_invoice_progress_chart(data):
	if not data: return None
	labels = [row['month'] for row in data]
	datasets = [{"name": _("Execution % This Period"),"values": [row['execution_percentage'] for row in data]},{"name": _("Cumulative Execution %"),"values": [row['cumulative_execution'] for row in data]}]
	return {"data": {"labels": labels, "datasets": datasets},"type": "bar","height": 300,"title": _("Invoice Progress (%)")}


# --- Functions for Financial Summary (Standard View) ---

def get_summary_columns(is_yearly_view):
	period_label = _("Year") if is_yearly_view else _("Month")
	return [
		{"label": period_label, "fieldname": "period", "fieldtype": "Data", "width": 180},
		{"label": _("Executed Value"), "fieldname": "executed_value", "fieldtype": "Currency", "width": 150},
		{"label": _("Total Purchases"), "fieldname": "total_purchases", "fieldtype": "Currency", "width": 150},
		{"label": _("Other Expenses"), "fieldname": "other_expenses", "fieldtype": "Currency", "width": 150},
		{"label": _("Profit or Loss"), "fieldname": "profit_loss", "fieldtype": "Currency", "width": 150},
		{"label": _("Commission"), "fieldname": "commission", "fieldtype": "Currency", "width": 150},
	]

def get_summary_data(filters, is_yearly_view):
	date_format = "'%%Y'" if is_yearly_view else "'%%Y-%%m'"
	
	sql_filters = {
		"company": filters.get("company"),
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date")
	}

	# Query 1: Get Executed Value
	executed_value_data = frappe.db.sql(f"""
		SELECT DATE_FORMAT(mp.report_month, {date_format}) AS period_group, SUM(ese.actual_executed_value) AS total_executed_value, mp.commission_percentage
		FROM `tabMonthly Productivity` mp JOIN `tabExecution Schedule Entry` ese ON mp.name = ese.parent
		WHERE mp.docstatus = 1 AND mp.company = %(company)s AND mp.report_month BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY period_group, mp.commission_percentage
	""", sql_filters, as_dict=1)

	# Query 2: Get Total Purchases from Purchase Invoices
	purchases_data = frappe.db.sql(f"""
		SELECT DATE_FORMAT(pi.posting_date, {date_format}) as period_group, SUM(pi.base_grand_total) as total_purchases
		FROM `tabPurchase Invoice` pi
		WHERE pi.docstatus = 1 AND pi.company = %(company)s AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY period_group
	""", sql_filters, as_dict=1)

	# --- MODIFIED: Query 3 now filters for accounts 62-69 ---
	other_expenses_data = frappe.db.sql(f"""
		SELECT DATE_FORMAT(je.posting_date, {date_format}) as period_group, SUM(jea.debit_in_account_currency) as total_other_expenses
		FROM `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON je.name = jea.parent
		WHERE je.docstatus = 1 AND je.company = %(company)s AND je.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND LEFT(jea.account, 2) IN ('62', '63', '64', '65', '66', '67', '68', '69')
		GROUP BY period_group
	""", sql_filters, as_dict=1)

	# --- Merge all data into a single dictionary ---
	period_summary = {}
	for row in executed_value_data:
		period = row.period_group
		if period not in period_summary: period_summary[period] = frappe._dict({"executed_value": 0, "total_purchases": 0, "other_expenses": 0})
		period_summary[period].executed_value += row.total_executed_value
		period_summary[period].commission_percentage = row.commission_percentage

	for row in purchases_data:
		period = row.period_group
		if period not in period_summary: period_summary[period] = frappe._dict({"executed_value": 0, "total_purchases": 0, "other_expenses": 0})
		period_summary[period].total_purchases += row.total_purchases

	for row in other_expenses_data:
		period = row.period_group
		if period not in period_summary: period_summary[period] = frappe._dict({"executed_value": 0, "total_purchases": 0, "other_expenses": 0})
		period_summary[period].other_expenses += row.total_other_expenses

	# --- Process the merged data ---
	report_data = []
	for period, values in sorted(period_summary.items()):
		profit_loss = values.executed_value - values.total_purchases - values.other_expenses
		commission = profit_loss * (values.get("commission_percentage", 0) / 100.0)
		year, month_num = (period, '01') if is_yearly_view else period.split('-')
		formatted_period = year if is_yearly_view else f"{_(month_name[int(month_num)])} {year}"
		report_data.append({"period": formatted_period, "executed_value": values.executed_value, "total_purchases": values.total_purchases, "other_expenses": values.other_expenses, "profit_loss": profit_loss, "commission": commission})

	chart = get_chart_data(report_data)
	summary = get_report_summary(report_data)
	
	if report_data:
		total_row = {"period": "<b>" + _("Total") + "</b>", "executed_value": summary[0]['value'], "total_purchases": sum(r.get("total_purchases", 0) for r in report_data), "other_expenses": sum(r.get("other_expenses", 0) for r in report_data), "profit_loss": summary[1]['value'], "commission": summary[2]['value']}
		report_data.append(total_row)
		
	return report_data, chart, summary

def get_chart_data(data):
	if not data: return None
	labels = [row['period'] for row in data if "Total" not in row.get("period", "")]
	datasets = [{"name": _("Executed Value"), "values": [r['executed_value'] for r in data if "Total" not in r.get("period","")]},{"name": _("Profit or Loss"), "values": [r['profit_loss'] for r in data if "Total" not in r.get("period","")]},{"name": _("Commission"), "values": [r['commission'] for r in data if "Total" not in r.get("period","")]}]
	return {"data": {"labels": labels, "datasets": datasets}, "type": "bar", "height": 300}

def get_report_summary(data):
	if not data: return None
	rows_to_sum = [row for row in data if "Total" not in row.get("period", "")]
	total_executed = sum(r.get("executed_value", 0) for r in rows_to_sum)
	total_profit = sum(r.get("profit_loss", 0) for r in rows_to_sum)
	total_commission = sum(r.get("commission", 0) for r in rows_to_sum)
	return [{"value": total_executed, "label": _("Total Executed Value"), "datatype": "Currency", "indicator": "Green" if total_executed >= 0 else "Red"},{"value": total_profit, "label": _("Total Profit / Loss"), "datatype": "Currency", "indicator": "Green" if total_profit >= 0 else "Red"},{"value": total_commission, "label": _("Total Commission"), "datatype": "Currency", "indicator": "Green" if total_commission >= 0 else "Red"},]
