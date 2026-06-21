# Copyright (c) 2026, amal@zimplify.tech and contributors
# For license information, please see license.txt

"""Tests for the doctype-agnostic OCR layer (no model / network required)."""

import unittest

from sunday_catechism.ocr import base
from sunday_catechism.ocr.base import heuristic_parse

# A representative field list, as `get_ocr_fields` would return it.
SAMPLE_FIELDS = [
	{"fieldname": "admission_no", "label": "Admission No", "type": "int", "fieldtype": "Int", "options": None},
	{"fieldname": "first_name", "label": "First Name", "type": "str", "fieldtype": "Data", "options": None},
	{
		"fieldname": "name_of_father",
		"label": "Name of Father",
		"type": "str",
		"fieldtype": "Data",
		"options": None,
	},
	{
		"fieldname": "fathers_phone",
		"label": "Father's Phone",
		"type": "str",
		"fieldtype": "Phone",
		"options": None,
	},
	{"fieldname": "address", "label": "Address", "type": "str", "fieldtype": "Data", "options": None},
	{
		"fieldname": "date_of_birth",
		"label": "Date of Birth",
		"type": "date",
		"fieldtype": "Date",
		"options": None,
	},
]


class TestNormalizeDraft(unittest.TestCase):
	def test_dates_normalised_to_iso(self):
		out = base.normalize_draft({"date_of_birth": "05/31/2015"}, SAMPLE_FIELDS)
		self.assertEqual(out["date_of_birth"], "2015-05-31")

	def test_unparseable_date_is_flagged_not_kept(self):
		out = base.normalize_draft({"date_of_birth": "sometime in spring"}, SAMPLE_FIELDS)
		self.assertNotIn("date_of_birth", out)
		self.assertIn("date_of_birth", out["_uncertain"])

	def test_int_coerced_and_bad_int_flagged(self):
		self.assertEqual(base.normalize_draft({"admission_no": " 0421 "}, SAMPLE_FIELDS)["admission_no"], 421)
		bad = base.normalize_draft({"admission_no": "A-12"}, SAMPLE_FIELDS)
		self.assertNotIn("admission_no", bad)
		self.assertIn("admission_no", bad["_uncertain"])

	def test_blank_and_null_like_values_dropped(self):
		out = base.normalize_draft({"first_name": "", "name_of_father": "null"}, SAMPLE_FIELDS)
		self.assertNotIn("first_name", out)
		self.assertNotIn("name_of_father", out)

	def test_unknown_keys_ignored(self):
		# A field the model hallucinated that isn't on this doctype must be dropped.
		out = base.normalize_draft({"nonexistent_field": "x", "first_name": "Mary"}, SAMPLE_FIELDS)
		self.assertNotIn("nonexistent_field", out)
		self.assertEqual(out["first_name"], "Mary")


class TestBuildSchema(unittest.TestCase):
	def test_schema_records_array_with_nullable_fields(self):
		schema = base.build_schema(SAMPLE_FIELDS)
		self.assertEqual(schema["required"], ["records"])
		props = schema["properties"]["records"]["items"]["properties"]
		for field in SAMPLE_FIELDS:
			self.assertIn("null", props[field["fieldname"]]["type"])


class TestBuildPrompt(unittest.TestCase):
	def test_prompt_lists_fields_and_doctype(self):
		prompt = base.build_prompt("Student", SAMPLE_FIELDS)
		self.assertIn("Student", prompt)
		self.assertIn("[admission_no]", prompt)
		self.assertIn("[date_of_birth]", prompt)


class TestPaddleParse(unittest.TestCase):
	def test_label_matching_longest_first(self):
		text = "\n".join(
			[
				"Admission No: 421",
				"First Name: Mary",
				"Name of Father: Joseph",
				"Father's Phone: +91-9207479535",
				"Address: 12 Church Road",
			]
		)
		draft = heuristic_parse(text, SAMPLE_FIELDS)
		self.assertEqual(draft["admission_no"], "421")
		# "Name of Father" must win over the shorter generic match.
		self.assertEqual(draft["name_of_father"], "Joseph")
		self.assertIn("9207479535", draft["fathers_phone"])
		self.assertEqual(draft["_raw_text"], text)
		self.assertIn("admission_no", draft["_uncertain"])


class TestGetOcrFieldsAgainstMeta(unittest.TestCase):
	"""Runs under `bench run-tests`, where the Student doctype meta is available."""

	def test_student_field_selection(self):
		fields = base.get_ocr_fields("Student")
		names = {f["fieldname"] for f in fields}
		# Editable data fields are included...
		self.assertIn("first_name", names)
		self.assertIn("date_of_birth", names)
		self.assertIn("admission_no", names)
		# ...small Link fields (enumerable options) like class are included too.
		self.assertIn("class", names)  # Link to Class (few records)
		# ...computed/read-only and Check fields are excluded.
		self.assertNotIn("full_name", names)  # read_only
		self.assertNotIn("active", names)  # Check


if __name__ == "__main__":
	unittest.main()
