// Copyright (c) 2026, amal@zimplify.tech and contributors
// For license information, please see license.txt
//
// Attendance register printing for the Class doctype:
//  - form view: "Print Register" button -> picks academic year -> preview -> download;
//  - list view: "Print Registers" bulk action -> a ZIP with one PDF per selected class.
// A single class is previewed before download; multiple classes download the ZIP directly
// (an archive can't be shown in an <iframe>).
//
// Loaded on every desk page via `app_include_js` (note the ".bundle.js" so `bench build`
// content-hashes it and browsers always pick up edits, like the OCR bundle).

frappe.provide("sunday_catechism.register");

(function () {
	const ns = sunday_catechism.register;
	const METHOD =
		"sunday_catechism.sunday_catechism.print.attendance_register.generate_registers";

	// Ask for the academic year (prefilled with the default), then open a preview.
	ns.prompt = function (class_names) {
		if (!class_names || !class_names.length) {
			frappe.msgprint(__("Please select at least one Class."));
			return;
		}

		const d = new frappe.ui.Dialog({
			title:
				class_names.length === 1
					? __("Print Attendance Register")
					: __("Print Attendance Registers ({0} classes)", [class_names.length]),
			fields: [
				{
					label: __("Academic Year"),
					fieldname: "academic_year",
					fieldtype: "Link",
					options: "Academic Year",
					reqd: 1,
				},
			],
			// A single class can be previewed in an iframe; a multi-class ZIP cannot, so
			// it downloads straight away.
			primary_action_label:
				class_names.length === 1 ? __("Preview") : __("Download ZIP"),
			primary_action(values) {
				d.hide();
				if (class_names.length === 1) {
					ns.preview(class_names, values.academic_year);
				} else {
					ns.download(class_names, values.academic_year);
				}
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
	};

	// Download straight to the browser: a single PDF, or a ZIP of one PDF per class.
	ns.download = function (class_names, academic_year) {
		const url = `/api/method/${METHOD}?${$.param({
			class_names: JSON.stringify(class_names),
			academic_year: academic_year,
		})}`;
		// The whitelisted method streams the file (response type "download").
		window.open(url);
	};

	// Show the rendered PDF inline in an <iframe>; the primary action downloads it.
	ns.preview = function (class_names, academic_year) {
		const base = `/api/method/${METHOD}`;
		const common = {
			class_names: JSON.stringify(class_names),
			academic_year: academic_year,
		};
		// preview=1 streams the PDF inline (Content-Disposition: inline) so it renders in
		// the iframe; the download link omits it so the browser saves the file.
		const preview_url = `${base}?${$.param({ ...common, preview: 1 })}`;
		const download_url = `${base}?${$.param(common)}`;

		const d = new frappe.ui.Dialog({
			title: __("Register Preview"),
			size: "extra-large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "preview",
					options: `<iframe src="${preview_url}" title="${__(
						"Register Preview"
					)}" style="width:100%; height:75vh; border:1px solid var(--border-color, #d1d8dd); border-radius:var(--border-radius, 6px);"></iframe>`,
				},
			],
			primary_action_label: __("Download PDF"),
			primary_action() {
				// The whitelisted method streams the PDF (response type "download").
				window.open(download_url);
			},
		});

		d.show();
	};
})();

// Form view: add the "Print Register" button under Actions.
frappe.ui.form.on("Class", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(
			__("Print Register"),
			() => sunday_catechism.register.prompt([frm.doc.name]),
			__("Actions")
		);
	},
});

// List view: add a "Print Registers" action for the selected rows.
frappe.listview_settings["Class"] = {
	onload(listview) {
		listview.page.add_actions_menu_item(
			__("Print Registers"),
			() => {
				// `true` -> return docnames only.
				const selected = listview.get_checked_items(true);
				sunday_catechism.register.prompt(selected);
			},
			false
		);
	},
};
