# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class AcademicYear(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		academic_year: DF.Data
		end_date: DF.Date
		is_default: DF.Check
		start_date: DF.Date
		term_1_end_date: DF.Date | None
	# end: auto-generated types

	def validate(self):
		if getdate(self.end_date) <= getdate(self.start_date):
			frappe.throw("End Date must be after Start Date")

		if self.term_1_end_date and not (
			getdate(self.start_date) < getdate(self.term_1_end_date) < getdate(self.end_date)
		):
			frappe.throw("Term 1 End Date must fall between the Start Date and End Date")

		if self.is_default:
			frappe.db.set_value(
				"Academic Year",
				{"name": ("!=", self.name), "is_default": 1},
				"is_default",
				0,
			)
