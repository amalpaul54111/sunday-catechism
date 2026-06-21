# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""OpenRouter (hosted vision LLM) OCR backend.

Sends the photo to OpenRouter's OpenAI-compatible Chat Completions API so any
vision model it hosts (Qwen-VL, Gemini, GPT, Claude, …) can be tried without
running anything locally. The schema is requested via JSON mode and validated
app-side, so it works across models that don't support strict json_schema.
"""

import json

import frappe
import requests
from frappe import _


def extract(image_b64: str, settings, schema: dict, prompt: str) -> list[dict]:
	api_key = settings.get_password("openrouter_api_key") if settings.get("openrouter_api_key") else None
	if not api_key:
		frappe.throw(_("Set an OpenRouter API Key in OCR Settings to use the OpenRouter engine."))

	url = (settings.get("openrouter_url") or "https://openrouter.ai/api/v1").rstrip("/")
	model = settings.get("openrouter_model") or "qwen/qwen2.5-vl-72b-instruct"
	timeout = settings.get("openrouter_timeout") or 120

	payload = {
		"model": model,
		"temperature": 0,
		"response_format": {"type": "json_object"},
		"messages": [
			{
				"role": "user",
				"content": [
					{"type": "text", "text": prompt},
					{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
				],
			}
		],
	}
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
		# Optional attribution headers OpenRouter recommends.
		"X-Title": "Sunday Catechism OCR",
	}

	try:
		resp = requests.post(
			f"{url}/chat/completions", json=payload, headers=headers, timeout=timeout
		)
		resp.raise_for_status()
	except requests.exceptions.RequestException as e:
		frappe.throw(
			_("Could not reach OpenRouter at {0}. Check the API key and model. ({1})").format(url, str(e))
		)

	try:
		content = resp.json()["choices"][0]["message"]["content"]
		data = json.loads(content)
	except (KeyError, IndexError, ValueError, TypeError):
		frappe.throw(_("OpenRouter returned a response that could not be read as data."))

	records = data.get("records") if isinstance(data, dict) else None
	return records or []
