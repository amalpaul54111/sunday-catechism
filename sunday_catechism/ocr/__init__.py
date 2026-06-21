# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""Photo-to-document OCR.

Public, whitelisted entry points used by the desk UI:

- `get_ocr_doctypes()` — the doctypes OCR is enabled for that the user may create.
- `extract_documents(doctype, file_url)` — read an uploaded image and return a
  list of normalised, doctype-shaped drafts for the user to review before saving.

Which doctypes are enabled is configured in OCR Settings; the field list for each
is derived from its meta (see `base.get_ocr_fields`). No doctype is hard-coded.
"""

import frappe
from frappe import _

from sunday_catechism.ocr import base


@frappe.whitelist()
def get_ocr_doctypes() -> list[str]:
	"""Enabled doctypes the current user is allowed to create."""
	return [
		dt for dt in base.get_enabled_doctypes() if frappe.has_permission(dt, "create")
	]


@frappe.whitelist()
def extract_documents(doctype: str, file_url: str) -> list[dict]:
	if not doctype or not file_url:
		frappe.throw(_("A doctype and an image are both required."))

	settings = base.get_settings()

	if doctype not in base.get_enabled_doctypes(settings):
		frappe.throw(_("OCR is not enabled for {0}. Add it in OCR Settings.").format(doctype))

	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("You are not allowed to create {0}.").format(doctype), frappe.PermissionError)

	fields = base.get_ocr_fields(doctype)
	if not fields:
		frappe.throw(_("No OCR-eligible fields were found on {0}.").format(doctype))

	path = base.get_file_path(file_url)
	engine = settings.engine or "Ollama"

	if engine == "PaddleOCR":
		from sunday_catechism.ocr import paddle_engine

		drafts = paddle_engine.extract(path, settings, fields)
	elif engine == "Tesseract":
		from sunday_catechism.ocr import tesseract_engine

		drafts = tesseract_engine.extract(path, settings, fields)
	else:
		from sunday_catechism.ocr import ollama_engine

		image_b64 = base.image_to_base64(path, settings.max_image_dimension or 1600)
		schema = base.build_schema(fields)
		prompt = base.build_prompt(doctype, fields, settings)
		drafts = ollama_engine.extract(image_b64, settings, schema, prompt)

	return [base.normalize_draft(d, fields) for d in drafts]
