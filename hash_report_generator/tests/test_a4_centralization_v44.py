import unittest
from hash_report_generator.pdf_object_rules import PAGE,page_geometry
from hash_report_generator.pagination_policy import pagination_config
from reportlab.lib.units import mm

class TestA4Centralization(unittest.TestCase):
    def test_js_pagination_margins_match_page(self):
        p=pagination_config()["minimum_margins_mm"]
        for side in ("top","bottom","left","right"):
            self.assertEqual(p[side],PAGE[f"{side}_mm"])
    def test_a4_width(self):
        self.assertAlmostEqual(page_geometry()["body_width_pt"],170*mm)
