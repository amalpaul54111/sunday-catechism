# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""Tesseract (classic OCR) backend.

`pytesseract` is a thin pure-Python wrapper around the native `tesseract`
binary, so it installs on any Python version (no compiled wheel) — making it the
reliable classic engine on bleeding-edge interpreters like 3.14, where
paddlepaddle/onnxruntime have no wheels. Tesseract returns plain text, which
`base.heuristic_parse` maps onto fields by label.
"""

import frappe
from frappe import _

from sunday_catechism.ocr import base


def extract(path: str, settings, fields: list[dict]) -> list[dict]:
	try:
		import pytesseract
		from PIL import Image
	except ImportError:
		frappe.throw(
			_(
				"pytesseract is not installed. Run `pip install pytesseract` in the bench "
				"environment and install the tesseract binary (e.g. `brew install tesseract` "
				"or `apt install tesseract-ocr`)."
			)
		)

	lang = settings.tesseract_lang or "eng"
	try:
		with Image.open(path) as img:
			text = pytesseract.image_to_string(img, lang=lang)
	except pytesseract.TesseractNotFoundError:
		frappe.throw(
			_(
				"The tesseract binary was not found. Install it (e.g. `brew install tesseract` "
				"or `apt install tesseract-ocr`) and ensure it is on PATH."
			)
		)

	return [base.heuristic_parse(text, fields)]
