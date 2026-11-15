"""Integration tests for both production profile presentation policies."""
import unittest
from copy import deepcopy
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from hash_report_generator.pdf_object_rules import apply_profile_presentation, _STYLE


def make_styles():
    return {name: ParagraphStyle(name) for name in ("title_style", "header_style", "legal_style")}


class SharedProfilePresentationTests(unittest.TestCase):
    def test_original_values_for_both_profiles(self):
        for profile in ("SINGLE", "COMBINED"):
            with self.subTest(profile=profile):
                result = apply_profile_presentation(make_styles(), profile)
                self.assertEqual(result["title_style"].fontSize, 14)
                self.assertEqual(result["title_style"].leading, 18)
                self.assertEqual(result["title_style"].alignment, 0)
                self.assertEqual(result["title_style"].textColor, colors.HexColor("#18354D"))
                self.assertEqual(result["legal_style"].textColor, colors.HexColor("#34465A"))

    def test_js_mutation_reaches_actual_paragraph_style(self):
        rules = deepcopy(_STYLE)
        rules["COMBINED_PRESENTATION"]["title_font_pt"] = 27
        rules["COMBINED_PRESENTATION"]["title_color"] = "#123456"
        actual = apply_profile_presentation(make_styles(), "COMBINED", rules=rules)
        self.assertEqual(actual["title_style"].fontSize, 27)
        self.assertEqual(actual["title_style"].textColor, colors.HexColor("#123456"))

    def test_missing_rules_fail_closed(self):
        rules = deepcopy(_STYLE)
        del rules["COMBINED_PRESENTATION"]["legal_color"]
        with self.assertRaises(KeyError):
            apply_profile_presentation(make_styles(), "COMBINED", rules=rules)
        with self.assertRaises(ValueError):
            apply_profile_presentation(make_styles(), "OTHER")
