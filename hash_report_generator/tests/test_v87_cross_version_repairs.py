"""Regression gates for defects found in the v80-v86 cross-version review."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from reportlab.lib.styles import ParagraphStyle
from hash_report_generator import style_loader
from hash_report_generator import hash_report_core as core
from hash_report_generator.pdf_object_rules import apply_profile_presentation, _STYLE


def styles():
    return {key: ParagraphStyle(key) for key in ("title_style", "header_style", "legal_style")}


class V87Repairs(unittest.TestCase):
    def test_metrics_use_one_coherent_import_snapshot(self):
        self.assertEqual(core._core_metric("FONT_SIZE_TITLE"), _STYLE["CORE_REPORT_METRICS"]["FONT_SIZE_TITLE"])
        with patch.object(style_loader, "load_styles", side_effect=AssertionError("Unexpected Node reload")):
            for key in _STYLE["CORE_REPORT_METRICS"]:
                self.assertEqual(core._core_metric(key), _STYLE["CORE_REPORT_METRICS"][key])

    def test_missing_profile_rule_does_not_mutate_styles(self):
        actual = styles()
        before = {k: (v.fontSize, v.leading, v.textColor, v.alignment) for k, v in actual.items()}
        broken = deepcopy(_STYLE)
        del broken["COMBINED_PRESENTATION"]["legal_color"]
        with self.assertRaises(KeyError):
            apply_profile_presentation(actual, "COMBINED", rules=broken)
        self.assertEqual(before, {k: (v.fontSize, v.leading, v.textColor, v.alignment) for k, v in actual.items()})

    def test_invalid_metric_does_not_mutate_styles(self):
        actual = styles()
        before = actual["title_style"].fontSize
        broken = deepcopy(_STYLE)
        broken["SINGLE_PRESENTATION"]["title_font_pt"] = -2
        with self.assertRaises(ValueError):
            apply_profile_presentation(actual, "SINGLE", rules=broken)
        self.assertEqual(before, actual["title_style"].fontSize)

    def test_missing_style_does_not_mutate_remaining_styles(self):
        actual = styles()
        del actual["legal_style"]
        before = actual["title_style"].fontSize
        with self.assertRaises(KeyError):
            apply_profile_presentation(actual, "SINGLE")
        self.assertEqual(before, actual["title_style"].fontSize)
