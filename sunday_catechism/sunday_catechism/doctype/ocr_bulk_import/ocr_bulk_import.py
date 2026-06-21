# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""OCR Bulk Import.

Runs the photo OCR pipeline over many images in a background job, then builds a
standard Frappe **Data Import** from the extracted rows so the user reviews and
creates the records through the normal Data Import preview (validation, inline
edit, mapping). The source photo is carried in an `ocr_source_photo` Attach Image
field added to the target doctype, so every created record links back to its image.
"""

import os
import zipfile

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.xlsxutils import make_xlsx

from sunday_catechism.ocr import base, extract_drafts

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SOURCE_PHOTO_FIELD = "ocr_source_photo"


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

		data_import: DF.Link | None
		document_type: DF.Link
		files: DF.Table[OCRBulkImportFile]
		photos_failed: DF.Int
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
		self.db_set("data_import", None)
		frappe.enqueue(
			"sunday_catechism.sunday_catechism.doctype.ocr_bulk_import.ocr_bulk_import.run_extraction",
			queue="long",
			timeout=3600,
			docname=self.name,
			enqueue_after_commit=True,
		)
		return True


def run_extraction(docname: str):
	"""Background entry point: OCR every photo and build a Data Import for review."""
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
	_ensure_source_photo_field(doc.document_type)

	images = _collect_images(doc)
	rows = [fieldnames + [SOURCE_PHOTO_FIELD]]  # header
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
				rows.append([clean.get(fn, "") for fn in fieldnames] + [file_url])
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

	data_import = _build_data_import(doc.document_type, rows) if extracted else None

	doc.reload()
	doc.set("results", results)
	doc.total_photos = len(images)
	doc.records_extracted = extracted
	doc.photos_failed = failed
	doc.data_import = data_import
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


def _build_data_import(doctype: str, rows: list[list]) -> str:
	"""Write the extracted rows to an xlsx and wrap it in a Data Import to review."""
	xlsx = make_xlsx(rows, "OCR Import")
	template = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"ocr-bulk-import-{frappe.generate_hash(length=8)}.xlsx",
			"is_private": 1,
			"content": xlsx.getvalue(),
		}
	).insert(ignore_permissions=True)

	data_import = frappe.get_doc(
		{
			"doctype": "Data Import",
			"reference_doctype": doctype,
			"import_type": "Insert New Records",
			"import_file": template.file_url,
		}
	).insert(ignore_permissions=True)
	return data_import.name


def _ensure_source_photo_field(doctype: str):
	"""Add an `ocr_source_photo` Attach Image field to the target doctype (once)."""
	if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": SOURCE_PHOTO_FIELD}):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_field

	create_custom_field(
		doctype,
		{
			"fieldname": SOURCE_PHOTO_FIELD,
			"label": "OCR Source Photo",
			"fieldtype": "Attach Image",
			"description": "The photo this record was OCR-imported from, for verification.",
		},
	)


def _publish(docname: str, status: str, done: int = 0, total: int = 0):
	frappe.publish_realtime(
		"ocr_bulk_progress",
		{"name": docname, "status": status, "done": done, "total": total},
		doctype="OCR Bulk Import",
		docname=docname,
	)
