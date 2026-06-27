import calendar

import frappe
from frappe.utils import add_days, escape_html, formatdate, getdate
from frappe.utils.user import get_system_managers


def notify_weekly_birthdays() -> None:
	"""Email System Managers the students celebrating a birthday this week.

	Runs every Saturday (see ``scheduler_events`` in hooks.py). The window is the
	current calendar week, Monday through the coming Sunday, so the team can wish
	the students on Sunday. Birthdays are matched on month/day, ignoring the year.
	"""
	today = getdate()
	# date.weekday(): Monday=0 .. Sunday=6, so this lands on the week's Monday
	# regardless of which day the job actually runs.
	week_start = add_days(today, -today.weekday())
	week_dates = [add_days(week_start, i) for i in range(7)]
	# (month, day) -> position in the week, used to match and to sort chronologically.
	order = {(d.month, d.day): i for i, d in enumerate(week_dates)}

	students = frappe.get_all(
		"Student",
		filters={"active": 1, "date_of_birth": ["is", "set"]},
		fields=["full_name", "date_of_birth", "class"],
	)

	is_leap = calendar.isleap(today.year)
	celebrants = []
	for s in students:
		dob = getdate(s.date_of_birth)
		month, day = dob.month, dob.day
		# Feb 29 birthdays are wished on Mar 1 in non-leap years.
		if month == 2 and day == 29 and not is_leap:
			month, day = 3, 1
		position = order.get((month, day))
		if position is not None:
			celebrants.append((position, s))

	if not celebrants:
		return

	celebrants.sort(key=lambda c: c[0])

	recipients = get_system_managers()
	if not recipients:
		return

	week_label = "{start} – {end}".format(
		start=formatdate(week_dates[0], "d MMM"),
		end=formatdate(week_dates[-1], "d MMM"),
	)

	rows = "".join(
		"<tr><td>{name}</td><td>{cls}</td><td>{dob}</td></tr>".format(
			name=escape_html(s.full_name or ""),
			cls=escape_html(s.get("class") or ""),
			dob=formatdate(s.date_of_birth, "d MMM"),
		)
		for _, s in celebrants
	)

	message = """
		<p>The following student(s) celebrate their birthday this week ({week}).
		Please wish them on Sunday 🎉</p>
		<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
			<thead>
				<tr><th align="left">Student</th><th align="left">Class</th><th align="left">Birthday</th></tr>
			</thead>
			<tbody>{rows}</tbody>
		</table>
	""".format(week=week_label, rows=rows)

	frappe.sendmail(
		recipients=recipients,
		subject="Student birthdays this week ({week})".format(week=week_label),
		message=message,
	)
