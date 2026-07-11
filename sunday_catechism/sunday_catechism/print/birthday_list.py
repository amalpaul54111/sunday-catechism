# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe.utils import add_days, cint, formatdate, getdate
from frappe.utils.pdf import get_pdf

TEMPLATE = "sunday_catechism/sunday_catechism/print/birthday_list.html"


def _week_groups(year: int, class_name: str | None = None, active_only: bool = True) -> list[dict]:
	"""Group students into the Mon–Sun week their birthday falls in for ``year``.

	Mirrors the "Student Birthdays by Week" report: birthdays match on month/day
	(ignoring birth year) and Feb 29 rolls to Mar 1 in non-leap years. Returns one
	dict per week (chronological), each holding its students sorted by birthday.
	"""
	is_leap = calendar.isleap(year)

	student_filters = {"date_of_birth": ["is", "set"]}
	if active_only:
		student_filters["active"] = 1
	if class_name:
		student_filters["class"] = class_name

	students = frappe.get_all(
		"Student",
		filters=student_filters,
		fields=["full_name", "date_of_birth", "class"],
	)

	groups: dict = {}
	for s in students:
		dob = getdate(s.date_of_birth)
		month, day = dob.month, dob.day
		if month == 2 and day == 29 and not is_leap:
			month, day = 3, 1
		birthday = getdate(f"{year}-{month:02d}-{day:02d}")
		# date.weekday(): Monday=0 .. Sunday=6
		week_start = add_days(birthday, -birthday.weekday())
		groups.setdefault(week_start, []).append(
			{
				"full_name": s.full_name,
				"student_class": s.get("class"),
				"birthday": birthday,
				"birthday_display": formatdate(birthday, "EEE, d MMM"),
			}
		)

	weeks = []
	for week_start in sorted(groups):
		week_end = add_days(week_start, 6)
		members = sorted(groups[week_start], key=lambda r: (r["birthday"], r["full_name"] or ""))
		weeks.append(
			{
				"start": week_start,
				"end": week_end,
				"label": "{start} – {end}".format(
					start=formatdate(week_start, "d MMM"),
					end=formatdate(week_end, "d MMM yyyy"),
				),
				"students": members,
			}
		)
	return weeks


@frappe.whitelist()
def generate_birthday_list(
	year: str | None = None,
	class_name: str | None = None,
	active_only: int = 1,
	preview: int = 0,
) -> None:
	"""Stream a grouped-by-week student birthday list as an A4 PDF.

	``preview`` (1/0) streams the PDF inline so it can be shown in an <iframe>;
	otherwise it is sent as a download. Used by the "Student Birthdays by Week"
	report's "Print (Grouped by Week)" button.
	"""
	if not frappe.has_permission("Student", "read"):
		frappe.throw("Not permitted to read Student", frappe.PermissionError)

	year = cint(year) or getdate().year
	weeks = _week_groups(
		year,
		class_name=class_name or None,
		active_only=bool(cint(active_only)),
	)

	html = frappe.render_template(
		TEMPLATE,
		{"year": year, "class_name": class_name or "", "weeks": weeks},
	)
	pdf = get_pdf(html, {"orientation": "Portrait", "page-size": "A4"})

	frappe.local.response.update(
		{
			# "pdf" -> inline (preview in an iframe); "download" -> save dialog.
			"type": "pdf" if cint(preview) else "download",
			"filename": f"Student-Birthdays-{year}.pdf",
			"filecontent": pdf,
		}
	)
