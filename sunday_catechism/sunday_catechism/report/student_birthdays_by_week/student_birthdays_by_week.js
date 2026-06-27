frappe.query_reports["Student Birthdays by Week"] = {
	filters: [
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1,
		},
		{
			fieldname: "class",
			label: __("Class"),
			fieldtype: "Link",
			options: "Class",
		},
		{
			fieldname: "active_only",
			label: __("Active Students Only"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
