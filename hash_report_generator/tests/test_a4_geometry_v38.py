import unittest
from reportlab.lib.units import mm
from hash_report_generator.a4_document import A4DocTemplate
from hash_report_generator.pdf_object_rules import PAGE, content_width_mm

class A4GeometryTests(unittest.TestCase):
    def test_full_available_width(self):
        self.assertAlmostEqual(content_width_mm(), 170)
    def test_frame_has_no_hidden_inset(self):
        doc=A4DocTemplate('/tmp/not-generated.pdf', pagesize=(210*mm,297*mm), leftMargin=20*mm,rightMargin=20*mm,topMargin=20*mm,bottomMargin=35*mm)
        frames=doc._makePageTemplates()[0].frames
        self.assertAlmostEqual(frames[0]._aW,170*mm)
        self.assertAlmostEqual(frames[0]._aH,242*mm)
    def test_footer_zone_is_reserved(self):
        self.assertGreaterEqual(PAGE['bottom_mm'],PAGE['footer_reserved_mm'])

if __name__=='__main__': unittest.main()
