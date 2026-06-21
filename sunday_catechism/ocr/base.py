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

# A Link field is offered to OCR (with its valid values enumerated) only when the
# linked doctype has at most this many records — otherwise the option list is too
# large to put in the prompt and OCR can't reliably pick from it.
MAX_LINK_OPTIONS = 50

_PHONE_RE = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")

DEFAULT_PROMPT_TEMPLATE = (
	"You are a careful data-entry assistant. The image is a {doctype} form, or a "
	"register/table listing several {doctype} records. Read it and extract the "
	"details of every {doctype} you can find.\n"
	"Return one object per record in the `records` array.\n"
	"Scan the WHOLE page top to bottom, including headers, footers, margins and any "
	"separate boxes such as 'For Office Use Only' — identifiers like admission/"
	"registration numbers and dates are often handwritten in those side boxes.\n"
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


def _link_options(link_doctype: str) -> str | None:
	"""Newline-joined valid values for a Link target, or None if unbounded/empty.

	Returns None when the linked doctype is missing, empty, or has more than
	``MAX_LINK_OPTIONS`` records (too many to enumerate in the prompt).
	"""
	if not link_doctype:
		return None
	try:
		count = frappe.db.count(link_doctype)
	except Exception:
		return None
	if not count or count > MAX_LINK_OPTIONS:
		return None
	names = frappe.get_all(link_doctype, pluck="name", order_by="name asc")
	return "\n".join(names) if names else None


def get_ocr_fields(doctype: str) -> list[dict]:
	"""Derive the OCR-eligible field list for a doctype from its meta.

	Skips read-only/hidden/virtual fields, ineligible fieldtypes (Check, Table,
	layout breaks, …) and a small ignore-list. Link fields are included when their
	target has a small, enumerable set of records (e.g. Class), with the valid
	values carried in `options` so the model picks from them. Each entry carries the
	coarse OCR `type`, the original `fieldtype`, and `options` (Select / Link).
	"""
	meta = frappe.get_meta(doctype)
	fields = []
	for df in meta.fields:
		if df.fieldname in IGNORE_FIELDS:
			continue
		if df.read_only or df.hidden or getattr(df, "is_virtual", 0) or not df.label:
			continue

		ocr_type = FIELDTYPE_TO_OCR.get(df.fieldtype)
		options = df.options if df.fieldtype == "Select" else None
		if df.fieldtype == "Link":
			options = _link_options(df.options)
			if not options:
				continue  # unbounded or empty link target — not OCR-friendly
			ocr_type = "str"
		if not ocr_type:
			continue

		fields.append(
			{
				"fieldname": df.fieldname,
				"label": df.label,
				"type": ocr_type,
				"fieldtype": df.fieldtype,
				"options": options,
			}
		)
	return fields


def build_schema(fields: list[dict]) -> dict:
	"""JSON schema handed to Ollama's `format` param to constrain the output."""
	json_type = {"str": "string", "int": "integer", "float": "number", "date": "string", "datetime": "string"}
	properties = {}
	for f in fields:
		prop = {"type": [json_type[f["type"]], "null"]}
		choices = [o.strip() for o in (f.get("options") or "").splitlines() if o.strip()]
		if choices:
			# Constrain Select/Link fields to their valid values (plus null).
			prop["enum"] = [*choices, None]
		properties[f["fieldname"]] = prop
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
	from PIL import Image, ImageOps

	with Image.open(path) as img:
		# Honour the photo's EXIF orientation before anything else — phone cameras
		# store rotation in metadata, and a sideways image OCRs to garbled text.
		img = ImageOps.exif_transpose(img)
		img = img.convert("RGB")
		if max_dimension and max(img.size) > max_dimension:
			img.thumbnail((max_dimension, max_dimension))
		buffer = io.BytesIO()
		img.save(buffer, format="JPEG", quality=85)
	return base64.b64encode(buffer.getvalue()).decode("ascii")


# Named crop regions (as fractional x1, y1, x2, y2 of the upright image) for the
# focus pass — a second, zoomed query for small fields the full-page pass misses.
_REGION_BOXES = {
	"Bottom": (0.0, 0.58, 1.0, 1.0),
	"Top": (0.0, 0.0, 1.0, 0.42),
	"Left": (0.0, 0.0, 0.5, 1.0),
	"Right": (0.5, 0.0, 1.0, 1.0),
	"Bottom Right": (0.5, 0.55, 1.0, 1.0),
	"Top Right": (0.5, 0.0, 1.0, 0.45),
	"Whole": (0.0, 0.0, 1.0, 1.0),
}


def crop_region_b64(path: str, region: str = "Bottom", max_dimension: int = 2048) -> str:
	"""Return a base64 JPEG of one region of the form, upscaled for detail.

	Used by the focus pass: the region is cropped from the EXIF-corrected image and
	scaled so its longest edge is ``max_dimension`` px, giving the vision model many
	more pixels on small/handwritten text (e.g. an admission number in a side box).
	"""
	from PIL import Image, ImageOps

	fx1, fy1, fx2, fy2 = _REGION_BOXES.get(region, _REGION_BOXES["Bottom"])
	with Image.open(path) as img:
		img = ImageOps.exif_transpose(img).convert("RGB")
		w, h = img.size
		crop = img.crop((int(w * fx1), int(h * fy1), int(w * fx2), int(h * fy2)))
		cw, ch = crop.size
		scale = max_dimension / max(cw, ch) if max(cw, ch) else 1
		if scale and scale != 1:
			crop = crop.resize((max(1, int(cw * scale)), max(1, int(ch * scale))))
		buffer = io.BytesIO()
		crop.save(buffer, format="JPEG", quality=92)
	return base64.b64encode(buffer.getvalue()).decode("ascii")


def build_focus_prompt(doctype: str, fields: list[dict]) -> str:
	"""Prompt for the focus pass: a zoomed crop, read only the given field(s)."""
	lines = [f"- {f['label']} [{f['fieldname']}]" for f in fields]
	return (
		f"This image is a zoomed-in crop of part of a {doctype} form (e.g. an "
		"'office use' box). Read ONLY the following field(s); the value may be "
		"handwritten. Use null for anything you cannot read confidently — never guess:\n"
		+ "\n".join(lines)
	)


def vision_extract(image_b64, settings, schema, prompt):
	"""Dispatch a vision-LLM extraction to the configured engine (Ollama or OpenRouter)."""
	if (settings.engine or "Ollama") == "OpenRouter":
		from sunday_catechism.ocr import openrouter_engine

		return openrouter_engine.extract(image_b64, settings, schema, prompt)

	from sunday_catechism.ocr import ollama_engine

	return ollama_engine.extract(image_b64, settings, schema, prompt)


def apply_focus_pass(doctype, path, settings, fields, drafts):
	"""Re-read configured fields from a zoomed crop when the main pass left them empty.

	Only runs when exactly one record was found (a single form, not a register), so
	the cropped region maps unambiguously to that record. Returns ``drafts`` mutated
	in place. Ollama-only — relies on the vision model reading the crop.
	"""
	raw = (settings.get("focus_fields") or "").replace(",", "\n")
	focus_names = {n.strip() for n in raw.splitlines() if n.strip()}
	if not focus_names or len(drafts) != 1:
		return drafts

	subset = [f for f in fields if f["fieldname"] in focus_names]
	if not subset:
		return drafts

	region = settings.get("focus_region") or "Bottom"
	crop_b64 = crop_region_b64(path, region)
	focus_recs = vision_extract(
		crop_b64, settings, build_schema(subset), build_focus_prompt(doctype, subset)
	)
	if focus_recs:
		found, draft = focus_recs[0], drafts[0]
		for f in subset:
			name = f["fieldname"]
			if draft.get(name) in (None, "", "null") and found.get(name) not in (None, "", "null"):
				draft[name] = found[name]
	return drafts


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
			val = str(value).strip()
			choices = [o.strip() for o in (field.get("options") or "").splitlines() if o.strip()]
			if choices:
				# Map to an exact valid value (case-insensitive); flag if no match so
				# the reviewer corrects a Link/Select the model invented or misread.
				match = next((o for o in choices if o.lower() == val.lower()), None)
				clean[name] = match or val
				if not match:
					uncertain.append(name)
			else:
				clean[name] = val

	if draft.get("_raw_text"):
		clean["_raw_text"] = draft["_raw_text"]
	clean["_uncertain"] = sorted(set(uncertain))
	return clean
