# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""OCR Bulk Import.

Runs the photo OCR pipeline over many images in a background job and stores the
extracted rows on the document. The user reviews and edits the values in an
editable grid on the form, then "Create Records" validates and inserts each row,
attaching the source photo to the record it creates as a native file attachment
(no per-doctype field required).
"""

import json
import os
import zipfile

import frappe
from frappe import _
from frappe.model.document import Document

from sunday_catechism.ocr import base, extract_drafts

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


class OCRBulkImport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from sunday_catechism.sunday_catechism.doctype.ocr_bulk_import_file.ocr_bulk_import_file import (
			OCRBulkImportFile,
		)
		from sunday_catechism.sunday_catechism.doctype.ocr_bulk_import_result.ocr_bulk_import_result import (
			OCRBulkImportResult,
		)

		document_type: DF.Link
		extracted_data: DF.Code | None
		files: DF.Table[OCRBulkImportFile]
		photos_failed: DF.Int
		records_created: DF.Int
		records_extracted: DF.Int
		results: DF.Table[OCRBulkImportResult]
		status: DF.Literal["Draft", "Extracting", "Ready for Review", "Completed", "Failed"]
		total_photos: DF.Int
		zip_file: DF.Attach | None
	# end: auto-generated types

	@frappe.whitelist()
	def start_extraction(self):
		"""Validate and enqueue the background extraction job."""
		if self.status == "Extracting":
			frappe.throw(_("This import is already running."))
		if self.document_type not in base.get_enabled_doctypes():
			frappe.throw(_("OCR is not enabled for {0}. Enable it in OCR DocType Config.").format(self.document_type))
		if not frappe.has_permission(self.document_type, "create"):
			frappe.throw(
				_("You are not allowed to create {0}.").format(self.document_type), frappe.PermissionError
			)
		if not (self.files or self.zip_file):
			frappe.throw(_("Add some photos or a ZIP of images first."))

		self.db_set("status", "Extracting")
		frappe.enqueue(
			"sunday_catechism.sunday_catechism.doctype.ocr_bulk_import.ocr_bulk_import.run_extraction",
			queue="long",
			timeout=3600,
			docname=self.name,
			enqueue_after_commit=True,
		)
		return True

	@frappe.whitelist()
	def create_records(self, rows):
		"""Insert the (reviewed/edited) rows as records, attaching each source photo.

		`rows` is a list of {"photo": url, "values": {fieldname: value}}. Returns a
		summary; rows that fail validation are kept in `extracted_data` (with the
		error) so the user can correct and retry.
		"""
		if not frappe.has_permission(self.document_type, "create"):
			frappe.throw(
				_("You are not allowed to create {0}.").format(self.document_type), frappe.PermissionError
			)
		rows = frappe.parse_json(rows)
		created = 0
		remaining = []

		for row in rows:
			values = {k: v for k, v in (row.get("values") or {}).items() if v not in (None, "")}
			# Savepoint per row so one failure rolls back only its own changes,
			# leaving already-created records intact.
			frappe.db.savepoint("ocr_row")
			try:
				doc = frappe.new_doc(self.document_type)
				doc.update(values)
				doc.insert()
				if row.get("photo"):
					_attach_photo(self.document_type, doc.name, row["photo"])
				created += 1
			except Exception as e:
				frappe.db.rollback(save_point="ocr_row")
				row["_error"] = str(e)
				remaining.append(row)

		stored = frappe.parse_json(self.extracted_data or "{}")
		stored["rows"] = remaining
		self.extracted_data = json.dumps(stored)
		self.records_created = (self.records_created or 0) + created
		self.status = "Completed" if not remaining else "Ready for Review"
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"created": created, "failed": len(remaining)}


def run_extraction(docname: str):
	"""Background entry point: OCR every photo into editable rows on the document."""
	doc = frappe.get_doc("OCR Bulk Import", docname)
	try:
		_extract_all(doc)
	except Exception:
		doc.db_set("status", "Failed")
		frappe.db.commit()
		_publish(docname, "Failed")
		frappe.log_error(frappe.get_traceback(), "OCR Bulk Import failed")
		raise


def _extract_all(doc):
	settings = base.get_settings()
	fields = base.get_ocr_fields(doc.document_type, settings)
	fieldnames = [f["fieldname"] for f in fields]
	columns = [
		{"fieldname": f["fieldname"], "label": f["label"], "type": f["type"], "options": f.get("options")}
		for f in fields
	]

	images = _collect_images(doc)
	data_rows = []
	results = []
	extracted = 0
	failed = 0

	for index, file_url in enumerate(images):
		try:
			drafts = extract_drafts(doc.document_type, file_url, settings)
			count = 0
			for draft in drafts:
				clean = {k: v for k, v in draft.items() if not k.startswith("_")}
				if not clean:
					continue
				data_rows.append({"photo": file_url, "values": {fn: clean.get(fn) for fn in fieldnames}})
				count += 1
			results.append(
				{
					"source_image": file_url,
					"status": "Extracted" if count else "No data",
					"records_extracted": count,
				}
			)
			extracted += count
		except Exception as e:
			failed += 1
			results.append({"source_image": file_url, "status": "Error", "message": str(e)[:1000]})
		_publish(doc.name, "Extracting", done=index + 1, total=len(images))

	doc.reload()
	doc.set("results", results)
	doc.total_photos = len(images)
	doc.records_extracted = extracted
	doc.photos_failed = failed
	doc.extracted_data = json.dumps({"columns": columns, "rows": data_rows})
	doc.status = "Ready for Review" if extracted else "Completed"
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	_publish(doc.name, doc.status, done=len(images), total=len(images))


def _collect_images(doc) -> list[str]:
	"""Return the list of image file URLs from the uploaded photos and/or ZIP."""
	urls = [row.image for row in doc.files if row.image]

	if doc.zip_file:
		zip_path = base.get_file_path(doc.zip_file)
		with zipfile.ZipFile(zip_path) as archive:
			for info in archive.infolist():
				if info.is_dir():
					continue
				name = info.filename
				base_name = os.path.basename(name)
				# Skip macOS archive junk (__MACOSX/, ._resource forks), hidden files,
				# and anything that isn't an image by extension.
				if name.startswith("__MACOSX/") or base_name.startswith("."):
					continue
				if os.path.splitext(base_name)[1].lower() not in IMAGE_EXTS:
					continue
				try:
					saved = frappe.get_doc(
						{
							"doctype": "File",
							"file_name": base_name,
							"is_private": 1,
							"content": archive.read(info),
							"attached_to_doctype": "OCR Bulk Import",
							"attached_to_name": doc.name,
						}
					).insert(ignore_permissions=True)
					urls.append(saved.file_url)
				except Exception:
					# Mislabelled / corrupt entry — skip it rather than fail the batch.
					frappe.log_error(frappe.get_traceback(), f"OCR Bulk Import: skipped {name}")
	return urls


def _attach_photo(doctype: str, docname: str, file_url: str):
	"""Add `file_url` as a file attachment on the given record (once)."""
	if frappe.db.exists(
		"File", {"file_url": file_url, "attached_to_doctype": doctype, "attached_to_name": docname}
	):
		return
	frappe.get_doc(
		{
			"doctype": "File",
			"file_url": file_url,
			"is_private": 1,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
		}
	).insert(ignore_permissions=True)


def _publish(docname: str, status: str, done: int = 0, total: int = 0):
	frappe.publish_realtime(
		"ocr_bulk_progress",
		{"name": docname, "status": status, "done": done, "total": total},
		doctype="OCR Bulk Import",
		docname=docname,
	)
