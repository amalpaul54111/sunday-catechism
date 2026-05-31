# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Student(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active: DF.Check
		address: DF.Data
		admission_no: DF.Int
		baptism_name: DF.Data
		date_of_baptism: DF.Date
		date_of_birth: DF.Date
		fathers_phone: DF.Phone | None
		first_name: DF.Data
		full_name: DF.Data | None
		last_name: DF.Data | None
		middle_name: DF.Data | None
		mothers_phone: DF.Phone | None
		name_of_father: DF.Data
		name_of_mother: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "Student"

	def validate(self):
		# Collect all name parts that actually have a value
		name_parts = [self.first_name, self.middle_name, self.last_name]

		# Filter out None or empty strings, then join with a space
		self.full_name = " ".join([part.strip() for part in name_parts if part])
