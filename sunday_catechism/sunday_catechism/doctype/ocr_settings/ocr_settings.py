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

		engine: DF.Literal["Ollama", "Tesseract", "PaddleOCR", "OpenRouter"]
		max_image_dimension: DF.Int
		ollama_model: DF.Data
		ollama_num_ctx: DF.Int
		ollama_timeout: DF.Int
		ollama_url: DF.Data
		openrouter_api_key: DF.Password | None
		openrouter_model: DF.Data
		openrouter_timeout: DF.Int
		openrouter_url: DF.Data
		paddle_lang: DF.Data
		paddle_timeout: DF.Int
		paddle_url: DF.Data
		tesseract_lang: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "OCR Settings"
