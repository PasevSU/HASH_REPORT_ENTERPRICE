"""Centralized style contract; fails closed when required global rules disappear."""
import unittest
from pathlib import Path
from hash_report_generator.style_loader import load_styles

ROOT = Path(__file__).resolve().parents[1]

class GlobalStyleContract(unittest.TestCase):
    def test_all_canonical_style_files_present(self):
        for name in ("00_page.js", "20_typography.js", "30_tables.js", "34_core_paragraphs.js", "35_core_metrics.js", "96_page_identity.js"):
            with self.subTest(name=name):
                self.assertTrue((ROOT / "style" / name).is_file())

    def test_shared_page_rules_are_a4(self):
        page = load_styles()["PAGE"]
        self.assertEqual((page["width_mm"], page["height_mm"]), (210, 297))
        self.assertEqual(page["frame_padding_pt"], 0)

    def test_global_core_metric_coverage(self):
        rules = load_styles()
        self.assertIn("CORE_REPORT_METRICS", rules)
        self.assertIn("CORE_PARAGRAPH_PRESENTATION", rules)
        for name in ("FONT_SIZE_TITLE", "FONT_SIZE_TABLE_TEXT", "LEADING_TABLE_HASH"):
            with self.subTest(name=name):
                self.assertGreater(rules["CORE_REPORT_METRICS"][name], 0)

    def test_generator_modules_do_not_define_canonical_js_rules(self):
        for module in ("hash_report_single.py", "hash_report_combined.py"):
            text = (ROOT / module).read_text(encoding="utf-8")
            with self.subTest(module=module):
                self.assertNotIn("CORE_REPORT_METRICS =", text)
                self.assertNotIn("CORE_PARAGRAPH_PRESENTATION =", text)

if __name__ == "__main__":
    unittest.main()
