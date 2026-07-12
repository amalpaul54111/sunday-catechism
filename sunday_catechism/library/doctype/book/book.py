# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Book(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from sunday_catechism.library.doctype.book_copy.book_copy import BookCopy

		author: DF.Data
		available_copies: DF.Int
		category: DF.Link | None
		copies: DF.Table[BookCopy]
		cover_image: DF.AttachImage | None
		isbn: DF.Data | None
		next_copy_seq: DF.Int
		publisher: DF.Data | None
		title: DF.Data
		total_copies: DF.Int
		year_published: DF.Int
	# end: auto-generated types

	_DOCTYPE_NAME = "Book"

	def validate(self):
		self._ensure_default_copy_row()
		self._assign_copy_ids()
		self._check_isbn_uniqueness()
		self._update_copy_summary()

	def _ensure_default_copy_row(self):
		if self.is_new() and not self.copies:
			self.append("copies", {"status": "Available"})

	def _assign_copy_ids(self):
		for row in self.copies:
			if not row.copy_id:
				self.next_copy_seq = (self.next_copy_seq or 0) + 1
				row.copy_id = f"{self.name}-{self.next_copy_seq}"

	def _check_isbn_uniqueness(self):
		if not self.isbn:
			return
		duplicate = frappe.db.exists("Book", {"isbn": self.isbn, "name": ("!=", self.name)})
		if duplicate:
			frappe.throw(_("Another Book ({0}) already has ISBN {1}.").format(duplicate, self.isbn))

	def _update_copy_summary(self):
		self.total_copies = len(self.copies)
		self.available_copies = sum(1 for row in self.copies if row.status == "Available")
