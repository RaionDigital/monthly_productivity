# Copyright (c) 2025, raion digital and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from frappe import _

class MonthlyProductivity(Document):
	# --- NEW: Validation method ---
	# This function runs automatically when you save or submit the document.
	def validate(self):
		# Use a dictionary to track the total percentage for each sales invoice in this document
		invoice_totals = {}
		for entry in self.productivity:
			if not entry.sales_invoice:
				continue

			# If we haven't seen this invoice yet in this document, get the total from all *other* submitted documents.
			if entry.sales_invoice not in invoice_totals:
				previous_total = get_previous_execution_total(entry.sales_invoice, self.name)
				invoice_totals[entry.sales_invoice] = previous_total

			# Add the percentage from the current row to its running total
			invoice_totals[entry.sales_invoice] += flt(entry.execution_percentage)

		# After checking all rows, validate the final totals for each invoice
		for invoice, total in invoice_totals.items():
			if total > 100:
				# If any total is over 100, block the save/submit and show an error.
				frappe.throw(
					_("Total Execution Percentage for Sales Invoice {0} cannot exceed 100%. The current total is {1}%.").format(
						frappe.bold(invoice), frappe.bold(total)
					),
					title=_("Validation Error")
				)


@frappe.whitelist()
def get_previous_execution_total(sales_invoice, current_doc_name):
	"""
	Calculates the sum of 'execution_percentage' for a given sales_invoice
	from all submitted 'Monthly Productivity' documents, excluding the current one.
	"""
	if not sales_invoice:
		return 0

	# We use a direct SQL query for efficiency.
	total_percentage = frappe.db.sql("""
		SELECT
			SUM(child.execution_percentage)
		FROM
			`tabExecution Schedule Entry` AS child
		JOIN
			`tabMonthly Productivity` AS parent ON child.parent = parent.name
		WHERE
			parent.name != %(current_doc_name)s
			AND parent.docstatus = 1
			AND child.sales_invoice = %(sales_invoice)s
	""", {
		"current_doc_name": current_doc_name,
		"sales_invoice": sales_invoice
	})

	return total_percentage[0][0] if total_percentage and total_percentage[0][0] else 0
