# Copyright (c) 2026, amal@zimplify.tech and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestBook(IntegrationTestCase):
	"""
	Integration tests for Book.
	Use this class for testing interactions between multiple components.
	"""

	def test_default_copy_row_is_created(self):
		book = frappe.get_doc({
			"doctype": "Book",
			"title": "Test Book Without Copies",
			"author": "Test Author",
		}).insert()

		self.assertEqual(len(book.copies), 1)
		self.assertEqual(book.copies[0].copy_id, f"{book.name}-1")
		self.assertEqual(book.total_copies, 1)
		self.assertEqual(book.available_copies, 1)

	def test_copy_ids_are_not_reused_after_deletion(self):
		book = frappe.get_doc({
			"doctype": "Book",
			"title": "Test Book With Copies",
			"author": "Test Author",
			"copies": [{"status": "Available"}, {"status": "Available"}, {"status": "Available"}],
		}).insert()

		self.assertEqual(
			[row.copy_id for row in book.copies],
			[f"{book.name}-1", f"{book.name}-2", f"{book.name}-3"],
		)

		book.copies = [row for row in book.copies if row.copy_id != f"{book.name}-2"]
		book.append("copies", {"status": "Available"})
		book.save()

		self.assertEqual(
			sorted(row.copy_id for row in book.copies),
			sorted([f"{book.name}-1", f"{book.name}-3", f"{book.name}-4"]),
		)

	def test_duplicate_isbn_is_rejected(self):
		frappe.get_doc({
			"doctype": "Book",
			"title": "First Book",
			"author": "Test Author",
			"isbn": "978-0-00-000000-1",
		}).insert()

		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({
				"doctype": "Book",
				"title": "Second Book",
				"author": "Test Author",
				"isbn": "978-0-00-000000-1",
			}).insert()

	def test_blank_isbn_does_not_collide(self):
		first = frappe.get_doc({
			"doctype": "Book",
			"title": "No ISBN Book One",
			"author": "Test Author",
		}).insert()
		second = frappe.get_doc({
			"doctype": "Book",
			"title": "No ISBN Book Two",
			"author": "Test Author",
		}).insert()

		self.assertNotEqual(first.name, second.name)
