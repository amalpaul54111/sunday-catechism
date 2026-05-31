# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Teacher(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		date_of_birth: DF.Date | None
		full_name: DF.Data
		phone: DF.Phone | None
		qualification: DF.Data | None
		years_of_experience: DF.Int
	# end: auto-generated types

	_DOCTYPE_NAME = "Teacher"
