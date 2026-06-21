# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OCRBulkImportResult(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		message: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		records_extracted: DF.Int
		source_image: DF.AttachImage | None
		status: DF.Literal["Extracted", "No data", "Error"]
	# end: auto-generated types

	pass
