import frappe

_NAME_FIELDS = ("first_name", "middle_name", "last_name", "baptism_name", "name_of_father", "name_of_mother")


def execute():
	students = frappe.get_all("Student", fields=["name"] + list(_NAME_FIELDS))
	for student in students:
		updates = {}
		for field in _NAME_FIELDS:
			value = student.get(field)
			if value:
				normalized = value.strip().title()
				if normalized != value:
					updates[field] = normalized

		if not updates:
			continue

		name_parts = [
			updates.get("first_name", student.get("first_name")),
			updates.get("middle_name", student.get("middle_name")),
			updates.get("last_name", student.get("last_name")),
		]
		updates["full_name"] = " ".join([p.strip() for p in name_parts if p])

		frappe.db.set_value("Student", student["name"], updates, update_modified=False)

	frappe.db.commit()
