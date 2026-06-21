# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""Ollama (vision LLM) OCR backend.

Sends the photo to a local Ollama server running a vision model (Qwen2.5-VL by
default) and asks it to return records as JSON, constrained by `schema`.
"""

import json

import frappe
import requests
from frappe import _


def extract(image_b64: str, settings, schema: dict, prompt: str) -> list[dict]:
	url = (settings.ollama_url or "http://ollama:11434").rstrip("/")
	model = settings.ollama_model or "qwen2.5vl:3b"
	timeout = settings.ollama_timeout or 120
	# Vision models tokenise the image into many tokens. Ollama's default context is
	# only 4096, which a higher-resolution photo overflows — the server then rejects
	# the request with HTTP 400 ("exceeds the available context size"). Raise it so
	# larger, more legible images fit (the model itself supports up to 128k).
	num_ctx = settings.get("ollama_num_ctx") or 8192

	payload = {
		"model": model,
		"stream": False,
		"format": schema,
		"options": {"temperature": 0, "num_ctx": num_ctx},
		"messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
	}

	try:
		resp = requests.post(f"{url}/api/chat", json=payload, timeout=timeout)
		resp.raise_for_status()
	except requests.exceptions.RequestException as e:
		frappe.throw(
			_("Could not reach the Ollama server at {0}. Is it running and the model pulled? ({1})").format(
				url, str(e)
			)
		)

	content = (resp.json().get("message") or {}).get("content", "")
	try:
		data = json.loads(content)
	except (ValueError, TypeError):
		frappe.throw(_("The OCR model returned a response that could not be read as data."))

	records = data.get("records") if isinstance(data, dict) else None
	return records or []
