// Copyright (c) 2026, amal@zimplify.tech and contributors
// For license information, please see license.txt

frappe.ui.form.on("OCR Bulk Import", {
	onload(frm) {
		// Restrict Document Type to OCR-enabled doctypes the user can create.
		frappe.xcall("sunday_catechism.ocr.get_ocr_doctypes").then((doctypes) => {
			frm.set_query("document_type", () => ({ filters: { name: ["in", doctypes || []] } }));
		});

		if (frm.__ocr_listener) return;
		frm.__ocr_listener = true;
		frappe.realtime.on("ocr_bulk_progress", (data) => {
			if (!data || data.name !== frm.doc.name) return;
			if (data.status === "Extracting") {
				frm.dashboard.set_headline(
					__("Extracting… {0} / {1} photos", [data.done, data.total])
				);
			} else {
				frm.reload_doc();
			}
		});
	},

	refresh(frm) {
		if (frm.is_new()) return;

		// Multi-file upload (computer / phone gallery / camera).
		frm.add_custom_button(__("Upload Photos"), () => {
			new frappe.ui.FileUploader({
				allow_multiple: true,
				restrictions: { allowed_file_types: ["image/*"] },
				make_attachments_public: false,
				on_success(file_doc) {
					frm.add_child("files", { image: file_doc.file_url });
					frm.refresh_field("files");
					frm.dirty();
				},
			});
		});

		if (frm.doc.status !== "Extracting") {
			frm.add_custom_button(__("Extract & Build Import"), () => {
				if (frm.is_dirty()) {
					frappe.show_alert({ message: __("Please save first."), indicator: "orange" });
					return;
				}
				frm.call("start_extraction").then((r) => {
					if (r && r.message) {
						frappe.show_alert({
							message: __("Extraction started in the background."),
							indicator: "blue",
						});
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
		}

		if (frm.doc.data_import) {
			frm.add_custom_button(__("Open Data Import to Review"), () => {
				frappe.set_route("Form", "Data Import", frm.doc.data_import);
			}).addClass("btn-primary");
		}

		// Headline status.
		if (frm.doc.status === "Extracting") {
			frm.dashboard.set_headline(__("Extracting photos… this runs in the background."));
		} else if (frm.doc.status === "Ready for Review" && frm.doc.data_import) {
			frm.dashboard.set_headline(
				__(
					"Extracted {0} record(s) from {1} photo(s) ({2} failed). Open the Data Import to review and create.",
					[frm.doc.records_extracted, frm.doc.total_photos, frm.doc.photos_failed]
				)
			);
		}
	},
});
