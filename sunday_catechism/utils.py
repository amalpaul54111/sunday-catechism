# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

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


def split_terms(sundays, term_1_end_date=None):
	"""Split an ordered Sunday list into two terms at ``term_1_end_date`` (inclusive).

	Term 1 holds every Sunday on or before ``term_1_end_date``; Term 2 holds the rest.
	When no split date is configured the weeks are divided as evenly as possible by
	count, so an unconfigured academic year still prints two balanced term pages.

	Returns ``(term_1_sundays, term_2_sundays)``.
	"""
	if not sundays:
		return [], []

	if term_1_end_date:
		cutoff = getdate(term_1_end_date)
		term1 = [s for s in sundays if s <= cutoff]
		term2 = [s for s in sundays if s > cutoff]
	else:
		mid = -(-len(sundays) // 2)  # ceil division — first term gets the spare week
		term1, term2 = sundays[:mid], sundays[mid:]

	return term1, term2


def chunk_sundays(sundays, max_per_page=9):
	"""Split an ordered Sunday list into balanced consecutive chunks for the internals pages.

	Each chunk holds at most ``max_per_page`` weeks; the chunks are sized as evenly as
	possible (e.g. 37 Sundays -> five pages of 8/8/7/7/7). Returns a list of dicts::

	    [{"sundays": [date, ...], "label": "31-May-26 – 26-Jul-26"}, ...]
	"""
	n = len(sundays)
	if not n:
		return []

	pages = -(-n // max_per_page)  # ceil division, no math import
	base, rem = divmod(n, pages)

	chunks = []
	i = 0
	for p in range(pages):
		size = base + (1 if p < rem else 0)
		group = sundays[i : i + size]
		i += size
		chunks.append(
			{
				"sundays": group,
				"label": f"{formatdate(group[0], 'd-MMM-yy')} – {formatdate(group[-1], 'd-MMM-yy')}",
			}
		)
	return chunks
