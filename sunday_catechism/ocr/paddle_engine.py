# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""PaddleOCR (classic OCR) backend — calls the official PaddleX OCR serving.

paddlepaddle (PaddleOCR's inference backend) has no wheels for very new Python
versions (e.g. 3.14), so it cannot run inside the Frappe bench env. Instead we
run the official `paddlex --serve --pipeline OCR` server in its own container
and reach it over HTTP — exactly like the Ollama engine. PaddleX returns the
recognised text lines, which `base.heuristic_parse` maps onto fields by label.

See docs/paddleocr/ (the service) and docs/compose.paddleocr.yaml (the overlay).
PaddleX serving API: POST /ocr with {"file": <base64>, "fileType": 1}; the texts
come back at result.ocrResults[].prunedResult.rec_texts.
"""

import frappe
import requests
from frappe import _

from sunday_catechism.ocr import base


def extract(image_b64: str, settings, fields: list[dict]) -> list[dict]:
	url = (settings.get("paddle_url") or "http://paddleocr:8080").rstrip("/")
	timeout = settings.get("paddle_timeout") or 120

	try:
		# fileType 1 = image; visualize=False skips the (large) rendered result image.
		resp = requests.post(
			f"{url}/ocr",
			json={"file": image_b64, "fileType": 1, "visualize": False},
			timeout=timeout,
		)
		resp.raise_for_status()
	except requests.exceptions.RequestException as e:
		frappe.throw(
			_("Could not reach the PaddleOCR service at {0}. Is the sidecar running? ({1})").format(
				url, str(e)
			)
		)

	results = (resp.json().get("result") or {}).get("ocrResults") or []
	lines: list[str] = []
	for res in results:
		pruned = res.get("prunedResult") or {}
		lines.extend(pruned.get("rec_texts") or [])

	return [base.heuristic_parse("\n".join(lines), fields)]
