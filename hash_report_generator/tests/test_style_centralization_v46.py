import unittest
from hash_report_generator.pdf_object_rules import BRIDGE_LAYOUT, page_geometry, css_text
from hash_report_generator.bridge.layout import _legal_qr_widths
from hash_report_generator.style_loader import load_styles

class CentralizationV46(unittest.TestCase):
    def test_loader_all_js(self):
        self.assertIn("header_identity", load_styles()["BRIDGE_LAYOUT"])
    def test_qr_width_is_a4(self):
        self.assertAlmostEqual(sum(_legal_qr_widths()), page_geometry()["body_width_pt"], places=4)
    def test_header_settings_are_central(self):
        self.assertGreater(BRIDGE_LAYOUT["header_identity"]["trailing_spacer_pt"],0)
    def test_css_pagination_is_js(self):
        self.assertIn("orphans:3;widows:3",css_text())
