# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

from collections import OrderedDict

from frappe.utils import add_days, formatdate, getdate


def get_sundays(start_date, end_date):
	"""Return an ordered list of ``datetime.date`` for every Sunday in [start_date, end_date].

	``start_date`` is snapped forward to the first Sunday on or after it, so the academic
	year boundaries configured on the Academic Year doctype drive the columns entirely.
	"""
	start, end = getdate(start_date), getdate(end_date)
	# Python weekday(): Monday=0 .. Sunday=6. Advance start to the first Sunday.
	current = add_days(start, (6 - start.weekday()) % 7)
	sundays = []
	while current <= end:
		sundays.append(current)
		current = add_days(current, 7)
	return sundays


def local_phone(phone):
	"""Return a phone number without its country code, for printing.

	Frappe's Phone control stores numbers as ``+<country>-<number>`` (e.g.
	``+91-9207479535``). For the register we only want the local part.
	"""
	if not phone:
		return ""
	phone = str(phone).strip()
	if phone.startswith("+") and "-" in phone:
		return phone.split("-", 1)[1].strip()
	return phone


def group_sundays_by_month(sundays):
	"""Group an ordered Sunday list into ordered month buckets for per-month layout.

	Returns a list of dicts so templates can iterate deterministically::

	    [{"key": "2026-05", "label": "May 2026", "sundays": [date, ...]}, ...]
	"""
	groups = OrderedDict()
	for d in sundays:
		key = f"{d.year}-{d.month:02d}"
		if key not in groups:
			groups[key] = {"key": key, "label": formatdate(d, "MMMM yyyy"), "sundays": []}
		groups[key]["sundays"].append(d)
	return list(groups.values())
