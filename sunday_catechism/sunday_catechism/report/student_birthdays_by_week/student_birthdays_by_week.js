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

	onload(report) {
		const METHOD =
			"sunday_catechism.sunday_catechism.print.birthday_list.generate_birthday_list";

		// Server-rendered PDF grouped by week (Frappe reports can't carry a custom Jinja
		// print, so we stream our own — same pattern as register printing).
		report.page.add_inner_button(__("Print (Grouped by Week)"), () => {
			const common = {
				year: frappe.query_report.get_filter_value("year"),
				class_name: frappe.query_report.get_filter_value("class") || "",
				active_only: frappe.query_report.get_filter_value("active_only") ? 1 : 0,
			};
			const base = `/api/method/${METHOD}`;
			// preview=1 -> inline (Content-Disposition: inline) so it renders in the iframe;
			// the download link omits it so the browser saves the file.
			const preview_url = `${base}?${$.param({ ...common, preview: 1 })}`;
			const download_url = `${base}?${$.param(common)}`;

			const d = new frappe.ui.Dialog({
				title: __("Birthday List Preview"),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "preview",
						options: `<iframe src="${preview_url}" title="${__(
							"Birthday List Preview"
						)}" style="width:100%; height:75vh; border:1px solid var(--border-color, #d1d8dd); border-radius:var(--border-radius, 6px);"></iframe>`,
					},
				],
				primary_action_label: __("Download PDF"),
				primary_action() {
					window.open(download_url);
				},
			});

			d.show();
		});
	},
};
