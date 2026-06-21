# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""PaddleOCR (classic OCR) backend.

PaddleOCR returns raw text lines with no notion of fields, so the shared
`base.heuristic_parse` maps them onto fields by label. Note: paddlepaddle has no
wheels for very new Python versions (e.g. 3.14) — use the Tesseract engine there.
"""

import frappe
from frappe import _

from sunday_catechism.ocr import base

# PaddleOCR loads a model into memory on first use; cache the instance per
# (lang, gpu) so repeated calls in the same worker stay fast.
_OCR_CACHE: dict = {}


def _get_engine(lang: str, use_gpu: bool):
	key = (lang or "en", bool(use_gpu))
	if key not in _OCR_CACHE:
		try:
			from paddleocr import PaddleOCR
		except ImportError:
			frappe.throw(
				_(
					"PaddleOCR is not installed (note: it has no wheels for Python 3.14). Run "
					"`pip install paddlepaddle paddleocr`, or switch the engine to Tesseract or "
					"Ollama in OCR Settings."
				)
			)
		_OCR_CACHE[key] = PaddleOCR(use_angle_cls=True, lang=key[0], use_gpu=key[1], show_log=False)
	return _OCR_CACHE[key]


def extract(path: str, settings, fields: list[dict]) -> list[dict]:
	engine = _get_engine(settings.paddle_lang, settings.paddle_use_gpu)
	result = engine.ocr(path, cls=True)

	lines = []
	for block in result or []:
		for line in block or []:
			lines.append(line[1][0])

	return [base.heuristic_parse("\n".join(lines), fields)]
