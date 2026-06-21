# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""Shared, doctype-agnostic helpers for the photo-to-document OCR feature.

Nothing here is hard-coded to a single doctype. `get_ocr_fields(doctype)` reads
the field list straight off the DocType meta, and the schema, prompt and
normalisation are all built from that list. Engines stay dumb: they get a
schema + prompt (Ollama) or a field list (PaddleOCR) and return raw drafts.
"""

import base64
import io
import re

import frappe

# Frappe fieldtype -> the coarse OCR type we normalise/serialise to.
# Types not listed here (Link, Check, Table, Attach, layout breaks, …) are
# treated as ineligible and skipped — OCR can't reliably fill them.
FIELDTYPE_TO_OCR = {
	"Data": "str",
	"Small Text": "str",
	"Text": "str",
	"Long Text": "str",
	"Text Editor": "str",
	"Phone": "str",
	"Select": "str",
	"Int": "int",
	"Float": "float",
	"Currency": "float",
	"Percent": "float",
	"Date": "date",
	"Datetime": "datetime",
}

# Eligible-by-type but never useful to OCR.
IGNORE_FIELDS = {"naming_series", "amended_from"}

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")

DEFAULT_PROMPT_TEMPLATE = (
	"You are a careful data-entry assistant. The image is a {doctype} form, or a "
	"register/table listing several {doctype} records. Read it and extract the "
	"details of every {doctype} you can find.\n"
	"Return one object per record in the `records` array.\n"
	"Extract these fields (use null for anything you cannot read confidently — "
	"never guess or invent a value):\n"
	"{fields}\n"
	"Phone numbers: digits only, keep any leading country code."
)


def get_settings():
	"""Return the OCR Settings single doc."""
	return frappe.get_single("OCR Settings")


def get_enabled_doctypes(settings=None) -> list[str]:
	"""DocTypes configured for OCR in OCR Settings (unfiltered by permission)."""
	settings = settings or get_settings()
	return [row.document_type for row in settings.enabled_doctypes if row.document_type]


def get_ocr_fields(doctype: str) -> list[dict]:
	"""Derive the OCR-eligible field list for a doctype from its meta.

	Skips read-only/hidden/virtual fields, ineligible fieldtypes (Link, Check,
	Table, layout breaks, …) and a small ignore-list. Each entry carries the
	coarse OCR `type`, the original `fieldtype`, and Select `options`.
	"""
	meta = frappe.get_meta(doctype)
	fields = []
	for df in meta.fields:
		if df.fieldname in IGNORE_FIELDS:
			continue
		if df.read_only or df.hidden or getattr(df, "is_virtual", 0):
			continue
		ocr_type = FIELDTYPE_TO_OCR.get(df.fieldtype)
		if not ocr_type or not df.label:
			continue
		fields.append(
			{
				"fieldname": df.fieldname,
				"label": df.label,
				"type": ocr_type,
				"fieldtype": df.fieldtype,
				"options": df.options if df.fieldtype == "Select" else None,
			}
		)
	return fields


def build_schema(fields: list[dict]) -> dict:
	"""JSON schema handed to Ollama's `format` param to constrain the output."""
	json_type = {"str": "string", "int": "integer", "float": "number", "date": "string", "datetime": "string"}
	properties = {f["fieldname"]: {"type": [json_type[f["type"]], "null"]} for f in fields}
	return {
		"type": "object",
		"properties": {
			"records": {
				"type": "array",
				"items": {"type": "object", "properties": properties},
			}
		},
		"required": ["records"],
	}


def build_prompt(doctype: str, fields: list[dict], settings=None) -> str:
	"""Generate the extraction prompt from the field list for `doctype`."""
	lines = []
	for f in fields:
		if f["type"] in ("date", "datetime"):
			hint = " (format YYYY-MM-DD)"
		elif f["type"] in ("int", "float"):
			hint = " (a number)"
		elif f["options"]:
			choices = ", ".join(o.strip() for o in f["options"].splitlines() if o.strip())
			hint = f" (one of: {choices})"
		else:
			hint = ""
		lines.append(f"- {f['label']} [{f['fieldname']}]{hint}")

	prompt = DEFAULT_PROMPT_TEMPLATE.format(doctype=doctype, fields="\n".join(lines))
	extra = ((settings or get_settings()).prompt_template or "").strip()
	if extra:
		prompt += "\n\nAdditional instructions:\n" + extra
	return prompt


def get_file_path(file_url: str) -> str:
	"""Resolve a File doc's url to an absolute path on disk."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	return file_doc.get_full_path()


def image_to_base64(path: str, max_dimension: int = 1600) -> str:
	"""Downscale the image and return it as a base64 JPEG string for the model."""
	from PIL import Image

	with Image.open(path) as img:
		img = img.convert("RGB")
		if max_dimension and max(img.size) > max_dimension:
			img.thumbnail((max_dimension, max_dimension))
		buffer = io.BytesIO()
		img.save(buffer, format="JPEG", quality=85)
	return base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_date(value):
	"""Best-effort parse of an arbitrary date string into an ISO date, or None."""
	from frappe.utils import getdate

	try:
		return getdate(value).isoformat()
	except Exception:
		pass
	try:
		from dateutil import parser

		return parser.parse(str(value), dayfirst=True).date().isoformat()
	except Exception:
		return None


def _parse_datetime(value):
	"""Best-effort parse into a 'YYYY-MM-DD HH:MM:SS' string, or None."""
	try:
		from dateutil import parser

		return parser.parse(str(value), dayfirst=True).strftime("%Y-%m-%d %H:%M:%S")
	except Exception:
		return None


def heuristic_parse(text: str, fields: list[dict]) -> dict:
	"""Map raw OCR text lines onto fields by searching for each field's label.

	Shared by the classic (non-LLM) engines, which return plain text with no
	field structure. Longer labels are matched first so 'Name of Father' wins
	over 'Name'. Every guessed value is flagged uncertain, and the full
	recognised text is kept as `_raw_text` as a safety net for the reviewer.
	"""
	draft: dict = {"_raw_text": text}
	# (lowercased label, field), longest label first.
	label_map = sorted(
		[(f["label"].lower(), f) for f in fields if f.get("label")],
		key=lambda pair: len(pair[0]),
		reverse=True,
	)

	for raw in text.splitlines():
		line = raw.strip()
		if not line:
			continue
		low = line.lower()
		value = line.split(":", 1)[1].strip() if ":" in line else ""

		for label, field in label_map:
			if label and label in low:
				name = field["fieldname"]
				if name in draft:
					break
				if field.get("fieldtype") == "Phone":
					m = _PHONE_RE.search(line)
					draft[name] = (m.group(1) if m else value).strip()
				else:
					draft[name] = value
				break

	draft["_uncertain"] = [k for k in draft if not k.startswith("_")]
	return draft


def normalize_draft(draft: dict, fields: list[dict]) -> dict:
	"""Coerce a raw engine draft into clean, doctype-shaped data.

	Dates/datetimes become canonical strings, numbers are coerced, blanks are
	dropped. Fields the engine flagged or that failed to coerce are collected in
	`_uncertain` so the review UI can highlight them. `_raw_text` is passed through.
	"""
	clean: dict = {}
	field_by_name = {f["fieldname"]: f for f in fields}
	uncertain = [u for u in (draft.get("_uncertain") or []) if u in field_by_name]

	for name, field in field_by_name.items():
		value = draft.get(name)
		if value in (None, "", "null", "None"):
			continue
		ocr_type = field["type"]
		if ocr_type == "date":
			parsed = _parse_date(value)
			if parsed:
				clean[name] = parsed
			else:
				uncertain.append(name)
		elif ocr_type == "datetime":
			parsed = _parse_datetime(value)
			if parsed:
				clean[name] = parsed
			else:
				uncertain.append(name)
		elif ocr_type == "int":
			try:
				clean[name] = int(str(value).strip())
			except (TypeError, ValueError):
				uncertain.append(name)
		elif ocr_type == "float":
			try:
				clean[name] = float(re.sub(r"[^\d.\-]", "", str(value)))
			except (TypeError, ValueError):
				uncertain.append(name)
		else:
			clean[name] = str(value).strip()

	if draft.get("_raw_text"):
		clean["_raw_text"] = draft["_raw_text"]
	clean["_uncertain"] = sorted(set(uncertain))
	return clean
