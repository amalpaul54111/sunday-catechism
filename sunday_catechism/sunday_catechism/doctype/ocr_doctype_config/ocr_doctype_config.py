# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OCRDocTypeConfig(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from sunday_catechism.sunday_catechism.doctype.ocr_field_mapping.ocr_field_mapping import (
			OCRFieldMapping,
		)

		document_type: DF.Link
		enabled: DF.Check
		field_mappings: DF.Table[OCRFieldMapping]
	# end: auto-generated types

	pass
