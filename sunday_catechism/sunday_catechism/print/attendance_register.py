# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import io
import zipfile

import frappe
from frappe.utils import cint
from frappe.utils.pdf import get_pdf

from sunday_catechism.utils import chunk_sundays, get_sundays, local_phone, split_terms

TEMPLATE = "sunday_catechism/sunday_catechism/print/attendance_register.html"


_ORDER_BY = {
	"Admission Number": "admission_no asc",
	"Full Name": "full_name asc",
}


def _register_context(class_name: str, ay, student_order: str = "Admission Number") -> dict:
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
		order_by=_ORDER_BY.get(student_order, "admission_no asc"),
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
	# layout can't auto-size, so we derive it: ~5px/char + padding, clamped).
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
		"total_rows": len(students) + 2,
	}


def _get_print_settings() -> dict:
	"""Return Register Print Settings as a plain dict, falling back to defaults."""
	int_defaults = {
		"table_font_size": 10,
		"vertical_header_font_size": 11,
		"cover_diocese_font_size": 16,
		"cover_title_font_size": 22,
		"cover_class_name_font_size": 56,
		"cover_class_label_font_size": 18,
		"cover_teacher_font_size": 30,
		"cover_teacher_label_font_size": 14,
		"cover_year_font_size": 20,
		"sheet_title_font_size": 13,
	}
	try:
		doc = frappe.get_single("Register Print Settings")
		settings = {k: int(getattr(doc, k) or v) for k, v in int_defaults.items()}
		settings["student_order"] = doc.student_order or "Admission Number"
		return settings
	except Exception:
		return {**int_defaults, "student_order": "Admission Number"}


def _build_register_pdf(class_name: str, ay) -> bytes:
	"""Render one class's attendance register as a landscape A4 PDF (raw bytes)."""
	ps = _get_print_settings()
	html = frappe.render_template(
		TEMPLATE,
		{"registers": [_register_context(class_name, ay, ps["student_order"])], "ps": ps},
	)
	return get_pdf(html, {"orientation": "Landscape", "page-size": "A4"})


def _safe_filename(class_name: str) -> str:
	return class_name.replace(" ", "-").replace("/", "-")


def _stream_registers(class_names: list[str], academic_year: str, preview: bool = False) -> None:
	"""Stream the register(s) for ``class_names`` to the browser.

	A single class is streamed as its own landscape A4 PDF; ``preview`` streams it inline
	(``Content-Disposition: inline``) so it can be shown in an <iframe>, otherwise it is
	sent as a download. Multiple classes are bundled into a ZIP of one PDF per class —
	never a single combined file — so each class can be saved or printed individually.
	"""
	if not frappe.has_permission("Class", "print"):
		frappe.throw("Not permitted to print Class", frappe.PermissionError)

	ay = frappe.get_doc("Academic Year", academic_year)

	if len(class_names) == 1:
		pdf = _build_register_pdf(class_names[0], ay)
		frappe.local.response.update(
			{
				# "pdf" -> inline (preview in an iframe); "download" -> save dialog.
				"type": "pdf" if preview else "download",
				"filename": f"Attendance-Register-{_safe_filename(class_names[0])}.pdf",
				"filecontent": pdf,
			}
		)
		return

	# One PDF per class, zipped together. Preview is meaningless for an archive, so the
	# ZIP is always downloaded regardless of the ``preview`` flag.
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
		for name in class_names:
			archive.writestr(
				f"Attendance-Register-{_safe_filename(name)}.pdf",
				_build_register_pdf(name, ay),
			)

	frappe.local.response.update(
		{
			"type": "download",
			"filename": f"Attendance-Registers-{len(class_names)}-Classes.zip",
			"filecontent": buffer.getvalue(),
			"content_type": "application/zip",
		}
	)


@frappe.whitelist()
def generate_registers(class_names: str, academic_year: str, preview: int = 0) -> None:
	"""Build attendance registers for one or more classes.

	``class_names`` is a JSON-encoded list (or a single name). A single class is returned
	as a PDF; multiple classes are returned as a ZIP holding one PDF per class (never a
	combined file). ``preview`` (1/0) streams a single class inline so the browser shows
	it in a viewer instead of downloading.
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
