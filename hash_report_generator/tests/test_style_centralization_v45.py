import unittest
from hash_report_generator.style_loader import load_styles
from hash_report_generator.pdf_object_rules import page_geometry, BRIDGE_LAYOUT
from hash_report_generator.bridge.layout import _legal_qr_widths
class StyleCentralizationTests(unittest.TestCase):
    def test_all_js_rules_discovered(self):
        self.assertIn("BRIDGE_LAYOUT", load_styles())
    def test_bridge_table_exactly_fits_body(self):
        self.assertAlmostEqual(sum(_legal_qr_widths()),page_geometry()["body_width_pt"],places=5)
    def test_bridge_qr_fits_column(self):
        self.assertGreater(_legal_qr_widths()[1],BRIDGE_LAYOUT["legal_qr"]["qr_size_mm"]*72/25.4)
    def test_all_sources_use_same_object(self):
        self.assertEqual(BRIDGE_LAYOUT,load_styles()["BRIDGE_LAYOUT"])
