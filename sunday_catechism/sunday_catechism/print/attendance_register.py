# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.pdf import get_pdf

from sunday_catechism.utils import chunk_sundays, get_sundays, local_phone

TEMPLATE = "sunday_catechism/sunday_catechism/print/attendance_register.html"


@frappe.whitelist()
def generate_register(class_name: str, academic_year: str) -> None:
	"""Build the landscape A4 attendance register PDF for a class and stream it to the browser.

	Sections: a decorative cover page, an attendance master sheet (one row per active
	student x one column per Sunday + exam columns) and a per-month internals sheet
	(Holy Mass / Academics / Assembly columns for each Sunday in the month).
	"""
	if not frappe.has_permission("Class", "print"):
		frappe.throw("Not permitted to print Class", frappe.PermissionError)

	klass = frappe.get_doc("Class", class_name)
	ay = frappe.get_doc("Academic Year", academic_year)
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

	# Width for the "Name of Student" column, sized to the longest name (the fixed table
	# layout can't auto-size, so we derive it: ~5px/char at the 8px font + padding, clamped).
	max_name_len = max((len(s["full_name"] or "") for s in students), default=12)
	name_col_px = min(max(max_name_len, 10), 28) * 5 + 8

	html = frappe.render_template(
		TEMPLATE,
		{
			"class_name": class_name,
			"teacher": teacher or "",
			"academic_year": ay.academic_year,
			"students": students,
			"sundays": sundays,
			"internal_pages": chunk_sundays(sundays),
			"name_col_px": name_col_px,
		},
	)

	pdf = get_pdf(html, {"orientation": "Landscape", "page-size": "A4"})

	safe_name = class_name.replace(" ", "-").replace("/", "-")
	frappe.local.response.update(
		{
			"type": "download",
			"filename": f"Attendance-Register-{safe_name}.pdf",
			"filecontent": pdf,
		}
	)
