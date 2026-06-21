# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class OCRSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from sunday_catechism.sunday_catechism.doctype.ocr_enabled_doctype.ocr_enabled_doctype import (
			OCREnabledDocType,
		)

		enabled_doctypes: DF.Table[OCREnabledDocType]
		engine: DF.Literal["Ollama", "Tesseract", "PaddleOCR"]
		max_image_dimension: DF.Int
		ollama_model: DF.Data
		ollama_timeout: DF.Int
		ollama_url: DF.Data
		paddle_lang: DF.Data
		paddle_use_gpu: DF.Check
		prompt_template: DF.SmallText | None
		tesseract_lang: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "OCR Settings"
