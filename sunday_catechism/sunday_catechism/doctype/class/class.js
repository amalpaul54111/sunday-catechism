// Copyright (c) 2026, amal@zimplify.tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Class", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(
			__("Print Register"),
			() => show_register_dialog(frm),
			__("Actions")
		);
	},
});

function show_register_dialog(frm) {
	const method =
		"sunday_catechism.sunday_catechism.print.attendance_register.generate_register";

	const d = new frappe.ui.Dialog({
		title: __("Print Attendance Register"),
		fields: [
			{
				label: __("Academic Year"),
				fieldname: "academic_year",
				fieldtype: "Link",
				options: "Academic Year",
				reqd: 1,
			},
		],
		primary_action_label: __("Generate PDF"),
		primary_action(values) {
			d.hide();
			const params = $.param({
				class_name: frm.doc.name,
				academic_year: values.academic_year,
			});
			// The whitelisted method streams the PDF (response type "download"),
			// so opening the URL hands it to the browser's PDF viewer / print.
			window.open(`/api/method/${method}?${params}`);
		},
	});

	// Prefill the default academic year, if one is marked default.
	frappe.db
		.get_value("Academic Year", { is_default: 1 }, "name")
		.then((r) => {
			if (r && r.message && r.message.name) {
				d.set_value("academic_year", r.message.name);
			}
		});

	d.show();
}
