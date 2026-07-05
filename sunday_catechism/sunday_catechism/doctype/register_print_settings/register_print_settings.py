# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class RegisterPrintSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		cover_class_label_font_size: DF.Int
		cover_class_name_font_size: DF.Int
		cover_diocese_font_size: DF.Int
		cover_teacher_font_size: DF.Int
		cover_teacher_label_font_size: DF.Int
		cover_title_font_size: DF.Int
		cover_year_font_size: DF.Int
		sheet_title_font_size: DF.Int
		table_font_size: DF.Int
		vertical_header_font_size: DF.Int
	# end: auto-generated types

	_DOCTYPE_NAME = "Register Print Settings"
