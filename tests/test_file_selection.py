"""Acceptance tests for the v5.5.2 explicit file selection.

Three layers are covered here, each with the smallest input that can prove the
claim:

* ``hash_report_generator/file_selection.py`` - the shared grammar (parsing,
  ordering, de-duplication, root, relative names, environment round-trip).
* ``hash_report_combined.py`` discovery - an explicit selection must return the
  chosen files and nothing else, must win over file type filters, and must fail
  closed instead of silently dropping a chosen file.
* ``chronoseal.pipeline`` - the guards that refuse contradictory requests before
  any work starts.

The reported set and the hashed set are the same set: that is the whole point of
the feature, so every test asserts on the discovered evidence list rather than on
the intermediate plumbing.
"""
import importlib.util
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _entry in (str(ROOT), str(ROOT / "hash_report_generator")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from hash_report_generator import file_selection as fs  # noqa: E402
from chronoseal.pipeline import Pipeline, PipelineError  # noqa: E402


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "combined_explicit_selection",
        ROOT / "hash_report_generator" / "hash_report_combined.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Evidence(unittest.TestCase):
    """Shared temporary evidence folder: top.txt, notes.pdf and nested/deep.txt."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name).resolve()
        (cls.root / "nested").mkdir()
        cls.top = cls.root / "top.txt"
        cls.note = cls.root / "notes.pdf"
        cls.deep = cls.root / "nested" / "deep.txt"
        for path in (cls.top, cls.note, cls.deep):
            path.write_bytes(b"evidence")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()


class ParseTests(_Evidence):
    def test_an_empty_request_means_no_selection(self):
        for value in (None, "", "   ", [], (), set()):
            self.assertEqual(fs.parse(value), [])

    def test_a_single_path_and_a_json_array_both_parse(self):
        self.assertEqual(fs.parse(str(self.top)), [self.top])
        self.assertEqual(fs.parse(self.top), [self.top])
        self.assertEqual(fs.parse(json.dumps([str(self.top), str(self.note)])), [self.top, self.note])

    def test_the_operators_order_is_preserved(self):
        self.assertEqual(fs.parse([self.deep, self.top]), [self.deep, self.top])

    def test_duplicates_collapse_case_insensitively(self):
        shouted = Path(str(self.top).upper())
        self.assertEqual(fs.parse([self.top, str(self.top), shouted]), [self.top])

    def test_blank_entries_are_skipped(self):
        self.assertEqual(fs.parse([self.top, None, "  "]), [self.top])

    def test_bytes_paths_are_decoded(self):
        self.assertEqual(fs.parse(os.fsencode(str(self.top))), [self.top])

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ValueError):
            fs.parse("['not', 'json'")

    def test_a_string_that_is_not_an_array_is_one_path(self):
        self.assertEqual(fs.parse(str(self.deep)), [self.deep])

    def test_an_unusable_type_is_rejected(self):
        with self.assertRaises(ValueError):
            fs.parse(12345)

    def test_the_size_limit_is_enforced(self):
        original = fs.MAX_FILES
        fs.MAX_FILES = 1
        try:
            with self.assertRaises(ValueError):
                fs.parse([self.top, self.note])
        finally:
            fs.MAX_FILES = original


class RootAndRelativeTests(_Evidence):
    def test_the_root_is_the_deepest_folder_holding_every_file(self):
        self.assertEqual(fs.root([self.top, self.note]), self.root)

    def test_nested_files_pull_the_root_down(self):
        self.assertEqual(fs.root([self.deep, self.root / "nested" / "other.txt"]),
                         self.root / "nested")

    def test_an_empty_selection_has_no_root(self):
        with self.assertRaises(ValueError):
            fs.root([])

    def test_relative_names_are_posix_and_anchor_based(self):
        mapping = fs.relative([self.top, self.deep], self.root)
        self.assertEqual(mapping[str(self.top)], "top.txt")
        self.assertEqual(mapping[str(self.deep)], "nested/deep.txt")

    def test_a_file_outside_the_anchor_keeps_an_absolute_name(self):
        mapping = fs.relative([self.deep], self.root / "nested")
        self.assertEqual(mapping[str(self.deep)], "deep.txt")
        outside = fs.relative([self.top], self.root / "nested")
        self.assertEqual(outside[str(self.top)], self.top.as_posix().lstrip("/"))

    def test_relative_keys_are_strings_so_the_manifest_stays_json_serialisable(self):
        # The mapping goes into the evidence manifest verbatim. A Path key made
        # json.dumps() raise "keys must be str, int, float, bool or None", which
        # aborted the archive pass after a fully signed report was already built.
        mapping = fs.relative([self.top, self.deep], self.root)
        self.assertTrue(all(isinstance(key, str) for key in mapping))
        self.assertIn("nested/deep.txt", json.dumps(mapping))

    def test_the_audit_payload_is_json_serialisable(self):
        json.dumps(fs.audit_payload([self.top, self.deep]))

    def test_entries_carry_path_and_relative_name(self):
        records = fs.entries([self.deep], self.root)
        self.assertEqual(records, [{"path": str(self.deep), "rel_path": "nested/deep.txt"}])

    @unittest.skipUnless(os.name == "nt", "drive letters only exist on Windows")
    def test_files_on_two_drives_have_no_common_root(self):
        with self.assertRaises(ValueError):
            fs.root([Path("C:/one/a.txt"), Path("D:/two/b.txt")])


class MissingAndEnvironmentTests(_Evidence):
    def test_missing_reports_absent_paths_in_order(self):
        absent = self.root / "gone.txt"
        self.assertEqual(fs.missing([absent, self.top]), [absent])

    def test_a_folder_is_not_a_selected_file(self):
        self.assertEqual(fs.missing([self.root]), [self.root])

    def test_the_environment_round_trip_is_lossless(self):
        unicode_file = self.root / "доказателство 1.txt"
        unicode_file.write_bytes(b"x")
        try:
            encoded = fs.to_env([self.top, unicode_file])
            self.assertNotIn("\\u", encoded)
            self.assertEqual(fs.from_env({fs.ENV_FILES: encoded}), [self.top, unicode_file])
        finally:
            unicode_file.unlink()

    def test_an_unset_variable_means_no_selection(self):
        self.assertEqual(fs.from_env({}), [])

    def test_describe_names_the_files_and_truncates(self):
        self.assertEqual(fs.describe([]), "no explicit file selection")
        self.assertIn("top.txt", fs.describe([self.top]))
        many = [self.root / f"file{index}.txt" for index in range(8)]
        self.assertIn("and 3 more", fs.describe(many))
        self.assertTrue(fs.describe(many).startswith("8 explicitly selected file(s)"))

    def test_the_audit_payload_is_machine_readable(self):
        self.assertEqual(fs.audit_payload([]), {"explicit_selection": False})
        payload = fs.audit_payload([self.top, self.deep])
        self.assertTrue(payload["explicit_selection"])
        self.assertEqual(payload["selection_count"], 2)
        self.assertEqual(payload["selection_root"], str(self.root))
        self.assertEqual(payload["selection_files"][1]["rel_path"], "nested/deep.txt")


class DiscoveryTests(_Evidence):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.generator_module = _load_generator()

    def _discover(self, selected, filters=None, recursive=False):
        env = {fs.ENV_FILES: fs.to_env(selected)} if selected is not None else {}
        with patch.dict(os.environ, env, clear=False):
            if selected is None:
                os.environ.pop(fs.ENV_FILES, None)
            generator = self.generator_module.CombinedReportGenerator(
                logging.getLogger("explicit-selection"), include_ots=False
            )
            return generator._discover_all_files_from_folder(
                self.root, recursive=recursive, filters=filters
            )

    def test_only_the_selected_files_are_discovered(self):
        names = {item["name"] for item in self._discover([self.top])}
        self.assertEqual(names, {"top.txt"})

    def test_the_panel_order_is_the_report_order(self):
        records = self._discover([self.note, self.top])
        self.assertEqual([item["name"] for item in records], ["notes.pdf", "top.txt"])

    def test_neighbour_files_are_never_admitted(self):
        names = {item["name"] for item in self._discover([self.top], recursive=True)}
        self.assertEqual(names, {"top.txt"})

    def test_a_selection_wins_over_file_type_filters(self):
        records = self._discover([self.top], filters=["*.pdf"])
        self.assertEqual([item["name"] for item in records], ["top.txt"])

    def test_nested_files_keep_their_relative_names(self):
        records = self._discover([self.deep])
        self.assertEqual([item["name"] for item in records], ["nested/deep.txt"])

    def test_a_generated_hash_report_is_never_re_admitted(self):
        report = self.root / "RPT-20260101-000000000-AAAABBBB_HASHREPORT_TYP_COMBO.pdf"
        report.write_bytes(b"%PDF-1.4\n")
        try:
            with self.assertRaises(RuntimeError) as caught:
                self._discover([report])
            self.assertIn("EXPLICIT_SELECTION_EMPTY", str(caught.exception))
        finally:
            report.unlink()

    def test_an_absent_selected_file_fails_closed(self):
        absent = self.root / "vanished.txt"
        with self.assertRaises(RuntimeError) as caught:
            self._discover([absent])
        self.assertIn("EXPLICIT_SELECTION_MISSING", str(caught.exception))
        self.assertIn("vanished.txt", str(caught.exception))

    def test_a_broken_environment_value_fails_closed(self):
        with patch.dict(os.environ, {fs.ENV_FILES: "[not json"}, clear=False):
            generator = self.generator_module.CombinedReportGenerator(
                logging.getLogger("explicit-selection"), include_ots=False
            )
            with self.assertRaises(RuntimeError) as caught:
                generator._discover_all_files_from_folder(self.root)
        self.assertIn("EXPLICIT_SELECTION_INVALID", str(caught.exception))

    def test_without_a_selection_folder_discovery_is_unchanged(self):
        names = {item["name"] for item in self._discover(None)}
        self.assertEqual(names, {"notes.pdf", "top.txt"})
        recursive = {item["name"] for item in self._discover(None, recursive=True)}
        self.assertEqual(recursive, {"notes.pdf", "top.txt", "nested/deep.txt"})

    def test_without_a_selection_the_filters_still_apply(self):
        names = {item["name"] for item in self._discover(None, filters=["*.pdf"])}
        self.assertEqual(names, {"notes.pdf"})


class PipelineGuardTests(_Evidence):
    def setUp(self):
        self.pipeline = Pipeline(ROOT, {}, log=lambda *_args: None)

    def test_filters_and_a_selection_cannot_be_combined(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.root, "combined", False, False, False, None,
                              ["*.pdf"], [str(self.top)])
        self.assertIn("cannot be", str(caught.exception))

    def test_a_selection_always_means_a_combined_report(self):
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.top, "single", False, False, False, None, None,
                              [str(self.top)])
        self.assertIn("combined report", str(caught.exception))

    def test_an_absent_selected_file_is_refused_before_any_work(self):
        absent = self.root / "vanished.txt"
        with self.assertRaises(PipelineError) as caught:
            self.pipeline.run(self.root, "combined", False, False, False, None, None,
                              [str(absent)])
        self.assertIn("no longer exist", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
