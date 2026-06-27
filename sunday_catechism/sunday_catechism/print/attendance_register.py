# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint
from frappe.utils.pdf import get_pdf

from sunday_catechism.utils import chunk_sundays, get_sundays, local_phone, split_terms

TEMPLATE = "sunday_catechism/sunday_catechism/print/attendance_register.html"

# Every sheet is padded to at least this many rows; the spare rows are left blank
# (only the serial number is filled) so a mid-year joiner can be written in later.
TARGET_ROWS = 24


def _register_context(class_name: str, ay) -> dict:
	"""Build the template context for one class's attendance register.

	Sections: a decorative cover page, an attendance master sheet (one row per active
	student x one column per Sunday + exam columns) and a per-month internals sheet
	(Holy Mass / Academics / Assembly columns for each Sunday in the month).
	"""
	klass = frappe.get_doc("Class", class_name)
	teacher = frappe.db.get_value("Teacher", klass.teacher, "full_name") if klass.teacher else ""

	students = frappe.get_all(
		"Student",
		filters={"class": class_name, "active": 1},
		fields=[
			"admission_no",
			"full_name",
			"address",
			"fathers_phone",
			"name_of_father",
			"name_of_mother",
			"date_of_birth",
			"baptism_name",
			"date_of_baptism",
		],
		order_by="admission_no asc",
	)

	# Strip country codes from phone numbers for printing.
	for student in students:
		student["fathers_phone"] = local_phone(student.get("fathers_phone"))

	sundays = get_sundays(ay.start_date, ay.end_date)

	# The attendance grid prints one page per term, split at the Academic Year's
	# Term 1 End Date. Each term page carries its own exam block; the last term also
	# carries the year-end summary (Total Marks / Pass-Fail).
	term_1_sundays, term_2_sundays = split_terms(sundays, ay.get("term_1_end_date"))
	terms = [
		{"label": "Term 1", "sundays": term_1_sundays, "exam": "Half Yearly Exam", "is_last": False},
		{"label": "Term 2", "sundays": term_2_sundays, "exam": "Final Exam", "is_last": True},
	]

	# Width for the "Name of Student" column, sized to the longest name (the fixed table
	# layout can't auto-size, so we derive it: ~5px/char at the 8px font + padding, clamped).
	max_name_len = max((len(s["full_name"] or "") for s in students), default=12)
	name_col_px = min(max(max_name_len, 10), 28) * 5 + 8

	return {
		"class_name": class_name,
		"teacher": teacher or "",
		"academic_year": ay.academic_year,
		"students": students,
		"sundays": sundays,
		"terms": terms,
		"internal_pages": chunk_sundays(sundays),
		"name_col_px": name_col_px,
		"total_rows": max(len(students), TARGET_ROWS),
	}


def _stream_registers(class_names: list[str], academic_year: str, preview: bool = False) -> None:
	"""Render the register(s) for ``class_names`` into one landscape A4 PDF and stream it.

	When several classes are passed each one's register starts on a fresh page (the
	template forces a page break between registers), so a whole grade prints as a single
	booklet. ``preview`` streams the PDF inline (``Content-Disposition: inline``) so it can
	be shown in an <iframe>; otherwise it is sent as a download.
	"""
	if not frappe.has_permission("Class", "print"):
		frappe.throw("Not permitted to print Class", frappe.PermissionError)

	ay = frappe.get_doc("Academic Year", academic_year)
	registers = [_register_context(name, ay) for name in class_names]

	html = frappe.render_template(TEMPLATE, {"registers": registers})
	pdf = get_pdf(html, {"orientation": "Landscape", "page-size": "A4"})

	if len(class_names) == 1:
		safe_name = class_names[0].replace(" ", "-").replace("/", "-")
		filename = f"Attendance-Register-{safe_name}.pdf"
	else:
		filename = f"Attendance-Registers-{len(class_names)}-Classes.pdf"

	frappe.local.response.update(
		{
			# "pdf" -> inline (preview in an iframe); "download" -> save dialog.
			"type": "pdf" if preview else "download",
			"filename": filename,
			"filecontent": pdf,
		}
	)


@frappe.whitelist()
def generate_registers(class_names: str, academic_year: str, preview: int = 0) -> None:
	"""Build attendance registers for one or more classes as a single PDF.

	``class_names`` is a JSON-encoded list (or a single name); the PDF bundles them in
	the given order, one register per class. ``preview`` (1/0) streams it inline so the
	browser shows it in a viewer instead of downloading.
	"""
	class_names = frappe.parse_json(class_names)
	if isinstance(class_names, str):
		class_names = [class_names]
	class_names = [name for name in (class_names or []) if name]
	if not class_names:
		frappe.throw("No classes selected")

	_stream_registers(class_names, academic_year, preview=bool(cint(preview)))


@frappe.whitelist()
def generate_register(class_name: str, academic_year: str, preview: int = 0) -> None:
	"""Single-class wrapper around :func:`generate_registers` (kept for existing links)."""
	_stream_registers([class_name], academic_year, preview=bool(cint(preview)))
