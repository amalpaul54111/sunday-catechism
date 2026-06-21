# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OCRFieldMapping(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		alias: DF.Data | None
		fieldname: DF.Data
		focus: DF.Check
		focus_region: DF.Literal["Bottom", "Top", "Left", "Right", "Bottom Right", "Top Right", "Whole"]
		hint: DF.SmallText | None
		include: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
	# end: auto-generated types

	pass
