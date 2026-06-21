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
				frm.dashboard.set_headline(__("Extracting… {0} / {1} photos", [data.done, data.total]));
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

		const can_extract = !["Extracting", "Ready for Review"].includes(frm.doc.status);
		if (can_extract) {
			frm.add_custom_button(__("Extract"), () => {
				if (frm.is_dirty()) {
					frappe.show_alert({ message: __("Please save first."), indicator: "orange" });
					return;
				}
				frm.call("start_extraction").then((r) => {
					if (r && r.message) {
						frappe.show_alert({ message: __("Extraction started…"), indicator: "blue" });
						frm.reload_doc();
					}
				});
			}).addClass("btn-primary");
		}

		// Headline + editable review grid.
		if (frm.doc.status === "Extracting") {
			frm.dashboard.set_headline(__("Extracting photos… this runs in the background."));
		} else if (frm.doc.status === "Ready for Review") {
			frm.dashboard.set_headline(
				__("Review and edit the rows below, then click Create Records.")
			);
			render_review(frm);
		}
	},
});

function render_review(frm) {
	const wrapper = frm.get_field("review").$wrapper;
	wrapper.empty();

	let parsed = {};
	try {
		parsed = JSON.parse(frm.doc.extracted_data || "{}");
	} catch (e) {
		// ignore
	}
	const columns = parsed.columns || [];
	const rows = parsed.rows || [];
	if (!rows.length) {
		wrapper.html(`<p class="text-muted">${__("No rows to review.")}</p>`);
		return;
	}

	const head = [
		`<th style="width:28px"></th>`,
		`<th style="width:28px">#</th>`,
		`<th style="width:64px">${__("Photo")}</th>`,
	]
		.concat(columns.map((c) => `<th>${frappe.utils.escape_html(c.label)}</th>`))
		.join("");

	const body = rows
		.map((row, i) => {
			const values = row.values || {};
			const cells = columns
				.map((c) => `<td>${cell_input(c, values[c.fieldname])}</td>`)
				.join("");
			const photo = row.photo
				? `<a href="${row.photo}" target="_blank" title="${__("Open photo")}">
						<img src="${row.photo}" style="width:48px;height:48px;object-fit:cover;border-radius:4px">
				   </a>`
				: "";
			const err = row._error
				? `<div class="text-danger small mt-1" style="white-space:normal">${frappe.utils.escape_html(
						row._error
				  )}</div>`
				: "";
			return `<tr data-photo="${frappe.utils.escape_html(row.photo || "")}">
						<td class="text-center"><button class="btn btn-xs btn-link text-danger ocr-del-row" title="${__(
							"Remove this row"
						)}">&times;</button></td>
						<td class="text-muted"><span class="ocr-rownum">${i + 1}</span>${err}</td>
						<td>${photo}</td>${cells}
					</tr>`;
		})
		.join("");

	wrapper.html(`
		<div class="table-responsive" style="max-height:60vh;overflow:auto">
			<table class="table table-bordered" style="font-size:12px;white-space:nowrap">
				<thead><tr>${head}</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</div>
		<button class="btn btn-primary btn-sm ocr-create-btn"></button>
	`);

	update_create_count(wrapper);
	wrapper.find(".ocr-create-btn").on("click", () => create_records(frm, columns));
	wrapper.on("click", ".ocr-del-row", function () {
		$(this).closest("tr").remove();
		update_create_count(wrapper);
	});
}

// Refresh the row numbers and the "Create N" button after rows are removed.
function update_create_count(wrapper) {
	const $rows = wrapper.find("tbody tr");
	$rows.each((idx, tr) => $(tr).find(".ocr-rownum").text(idx + 1));
	const n = $rows.length;
	wrapper
		.find(".ocr-create-btn")
		.text(__("Create {0} Record(s)", [n]))
		.prop("disabled", n === 0);
}

// Build an editable cell: a <select> for fields with a fixed option set
// (Select / small Link), a date input for dates, otherwise a text input.
function cell_input(col, value) {
	const field = frappe.utils.escape_html(col.fieldname);
	const val = value == null ? "" : String(value);
	const opts = (col.options || "")
		.split("\n")
		.map((o) => o.trim())
		.filter(Boolean);

	if (opts.length) {
		const options = [`<option value=""></option>`]
			.concat(
				opts.map((o) => {
					const e = frappe.utils.escape_html(o);
					return `<option value="${e}"${o === val ? " selected" : ""}>${e}</option>`;
				})
			)
			.join("");
		return `<select class="form-control input-xs ocr-cell" data-field="${field}" style="min-width:130px">${options}</select>`;
	}

	const type = col.type === "date" ? "date" : "text";
	const width = col.type === "date" ? 140 : 170;
	return `<input type="${type}" class="form-control input-xs ocr-cell" data-field="${field}" style="min-width:${width}px" value="${frappe.utils.escape_html(
		val
	)}">`;
}

function create_records(frm, columns) {
	const rows = [];
	frm.get_field("review").$wrapper.find("tbody tr").each(function () {
		const $tr = $(this);
		const values = {};
		$tr.find(".ocr-cell").each(function () {
			values[$(this).attr("data-field")] = $(this).val();
		});
		rows.push({ values: values, photo: $tr.attr("data-photo") || null });
	});

	frappe.confirm(
		__("Create {0} record(s) in {1}? Rows that fail validation stay here to fix.", [
			rows.length,
			frm.doc.document_type,
		]),
		() => {
			frm.call({
				method: "create_records",
				args: { rows: JSON.stringify(rows) },
				freeze: true,
				freeze_message: __("Creating records…"),
			}).then((r) => {
				const m = r.message || {};
				frappe.show_alert({
					message: __("Created {0}, {1} failed.", [m.created || 0, m.failed || 0]),
					indicator: m.failed ? "orange" : "green",
				});
				frm.reload_doc();
			});
		}
	);
}
