// Copyright (c) 2026, amal@zimplify.tech and contributors
// For license information, please see license.txt
//
// Adds a generic "Import from Photo" button to the list view of every doctype
// enabled in OCR Settings. Loaded on every desk page via `app_include_js`.

frappe.provide("sunday_catechism.ocr");

(function () {
	const state = sunday_catechism.ocr;
	state.doctypes = []; // doctypes the user may OCR-import into

	function init() {
		frappe
			.xcall("sunday_catechism.ocr.get_ocr_doctypes")
			.then((doctypes) => {
				state.doctypes = doctypes || [];
				if (!state.doctypes.length) return;
				// Add on every route change, and once for the current view.
				frappe.router.on("change", maybe_add_button);
				maybe_add_button();
			})
			.catch(() => {
				/* OCR Settings not migrated yet, or no access — silently skip. */
			});
	}

	// On a List route for an enabled doctype, attach the button once cur_list is ready.
	function maybe_add_button() {
		const route = frappe.get_route();
		if (!route || route[0] !== "List") return;
		const doctype = route[1];
		if (!state.doctypes.includes(doctype)) return;
		attach_when_ready(doctype, 0);
	}

	function attach_when_ready(doctype, tries) {
		const list = window.cur_list;
		if (!list || list.doctype !== doctype) {
			if (tries < 25) setTimeout(() => attach_when_ready(doctype, tries + 1), 200);
			return;
		}
		if (list.__ocr_btn_added) return; // guard against duplicates
		list.__ocr_btn_added = true;
		list.page.add_inner_button(__("📷 Import from Photo"), () => open_ocr_dialog(list, doctype));
	}

	function open_ocr_dialog(listview, doctype) {
		const dialog = new frappe.ui.Dialog({
			title: __("Import {0} from Photo", [__(doctype)]),
			fields: [
				{
					fieldtype: "Attach Image",
					fieldname: "photo",
					label: __("Photo of a form or register"),
					reqd: 1,
				},
				{ fieldtype: "HTML", fieldname: "status" },
			],
			primary_action_label: __("Extract"),
			primary_action(values) {
				dialog.fields_dict.status.$wrapper.html(
					`<p class="text-muted">${__(
						"Reading the image locally… this can take 20–40 seconds."
					)}</p>`
				);
				dialog.get_primary_btn().prop("disabled", true);

				frappe.call({
					method: "sunday_catechism.ocr.extract_documents",
					args: { doctype: doctype, file_url: values.photo },
					callback(r) {
						dialog.hide();
						const drafts = (r.message || []).filter(has_any_field);
						if (!drafts.length) {
							frappe.msgprint(__("No details could be read from that image."));
							return;
						}
						if (drafts.length === 1) {
							open_in_new_form(doctype, drafts[0]);
						} else {
							review_multiple(doctype, drafts, listview);
						}
					},
					error() {
						dialog.get_primary_btn().prop("disabled", false);
						dialog.fields_dict.status.$wrapper.empty();
					},
				});
			},
		});
		dialog.show();
	}

	// A draft's real fields are every key that isn't an internal `_` marker.
	function clean_values(draft) {
		const values = {};
		Object.keys(draft).forEach((k) => {
			if (!k.startsWith("_") && draft[k] != null && draft[k] !== "") values[k] = draft[k];
		});
		return values;
	}

	function has_any_field(draft) {
		return Object.keys(clean_values(draft)).length > 0;
	}

	// Single record: open a pre-filled new form for review before saving.
	function open_in_new_form(doctype, draft) {
		frappe.new_doc(doctype, clean_values(draft));
		const uncertain = draft._uncertain || [];
		const msg = uncertain.length
			? __("Review and correct the highlighted fields before saving: {0}", [uncertain.join(", ")])
			: __("Review the details and save.");
		frappe.show_alert({ message: msg, indicator: uncertain.length ? "orange" : "blue" }, 8);
	}

	// Multiple records (register/table): list them and bulk-create on confirm.
	function review_multiple(doctype, drafts, listview) {
		// Build columns from the fields actually present, capped for readability.
		const keys = [];
		drafts.forEach((d) =>
			Object.keys(clean_values(d)).forEach((k) => {
				if (!keys.includes(k)) keys.push(k);
			})
		);
		const cols = keys.slice(0, 4);

		const header = cols
			.map((k) => `<th>${frappe.utils.escape_html(frappe.model.unscrub(k))}</th>`)
			.join("");
		const rows = drafts
			.map((d, i) => {
				const flagged = (d._uncertain || []).length ? ` <span class="text-warning">⚠</span>` : "";
				const cells = cols
					.map((k) => `<td>${frappe.utils.escape_html(d[k] != null ? String(d[k]) : "")}</td>`)
					.join("");
				return `<tr><td>${i + 1}${flagged}</td>${cells}</tr>`;
			})
			.join("");

		const dialog = new frappe.ui.Dialog({
			title: __("{0} records found", [drafts.length]),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p class="text-muted">${__(
						"OCR is not perfect — created records may need correcting. ⚠ marks low-confidence reads."
					)}</p>
					<table class="table table-bordered"><thead><tr><th>#</th>${header}</tr></thead>
					<tbody>${rows}</tbody></table>`,
				},
			],
			primary_action_label: __("Create {0} records", [drafts.length]),
			primary_action() {
				dialog.hide();
				bulk_create(doctype, drafts, listview);
			},
		});
		dialog.show();
	}

	async function bulk_create(doctype, drafts, listview) {
		let created = 0;
		const errors = [];
		for (const draft of drafts) {
			try {
				await frappe.db.insert({ doctype: doctype, ...clean_values(draft) });
				created += 1;
			} catch (e) {
				errors.push(e.message || String(e));
			}
		}

		frappe.show_alert(
			{
				message: __("Created {0} of {1} records.", [created, drafts.length]),
				indicator: errors.length ? "orange" : "green",
			},
			7
		);
		if (errors.length) {
			frappe.msgprint({
				title: __("Some records were not created"),
				message: errors.join("<br>"),
				indicator: "orange",
			});
		}
		listview.refresh();
	}

	$(document).on("app_ready", init);
})();
