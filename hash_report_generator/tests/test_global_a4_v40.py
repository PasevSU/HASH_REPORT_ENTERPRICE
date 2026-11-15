import unittest
from reportlab.lib.units import mm
from hash_report_generator.pdf_object_rules import PAGE,page_geometry,content_width_mm,css_text
from hash_report_generator.a4_document import A4DocTemplate
class GlobalA4Tests(unittest.TestCase):
    def test_coordinates(self):
        g=page_geometry()
        self.assertAlmostEqual(g['body_x_pt'],20*mm)
        self.assertAlmostEqual(g['body_y_pt'],PAGE['bottom_mm']*mm)
        self.assertAlmostEqual(g['body_width_pt'],170*mm)
        self.assertAlmostEqual(g['body_height_pt'],(PAGE['height_mm']-PAGE['top_mm']-PAGE['bottom_mm'])*mm)
        self.assertLessEqual(g['footer_top_pt']+PAGE['body_footer_gap_mm']*mm,g['body_y_pt'])
    def test_no_double_footer_reservation_css(self):
        self.assertIn(f"margin: 20mm 20mm {PAGE['bottom_mm']}mm 20mm",css_text())
    def test_template_rejects_drift(self):
        with self.assertRaises(ValueError):
            A4DocTemplate('/tmp/unused.pdf',leftMargin=21*mm)
    def test_table_width_single_source(self):
        from hash_report_generator.hash_report_core import ReportConstants
        self.assertAlmostEqual(ReportConstants.TABLE_WIDTH_MM,content_width_mm())
if __name__=='__main__': unittest.main()
