import calendar

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	filters = filters or {}
	year = int(filters.get("year") or getdate().year)
	is_leap = calendar.isleap(year)

	student_filters = {"date_of_birth": ["is", "set"]}
	if filters.get("active_only"):
		student_filters["active"] = 1
	if filters.get("class"):
		student_filters["class"] = filters.get("class")

	students = frappe.get_all(
		"Student",
		filters=student_filters,
		fields=["admission_no", "full_name", "date_of_birth", "class"],
	)

	data = []
	for s in students:
		dob = getdate(s.date_of_birth)
		month, day = dob.month, dob.day
		# Feb 29 birthdays are celebrated on Mar 1 in non-leap years.
		if month == 2 and day == 29 and not is_leap:
			month, day = 3, 1
		birthday = getdate(f"{year}-{month:02d}-{day:02d}")
		data.append(
			{
				"birthday": birthday,
				"full_name": s.full_name,
				"student_class": s.get("class"),
			}
		)

	# Order chronologically by the birthday.
	data.sort(key=lambda r: (r["birthday"], r["full_name"] or ""))

	return get_columns(), data


def get_columns():
	return [
		{
			"fieldname": "birthday",
			"label": _("Birthday"),
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"fieldname": "full_name",
			"label": _("Student"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "student_class",
			"label": _("Class"),
			"fieldtype": "Link",
			"options": "Class",
			"width": 150,
		},
	]
