import unittest
import tempfile
from pathlib import Path
from reportlab.pdfgen import canvas
from chronoseal.report_quality import audit_layout

class LayoutGateTests(unittest.TestCase):
    def test_clean_body_and_footer(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'clean.pdf'
            c = canvas.Canvas(str(p), pagesize=(595.2756, 841.8898))
            for i in range(15):
                c.drawString(75, 700-i*15, 'Evidence report content line %d' % i)
            c.drawString(75, 20, 'Page 1/1')
            c.save()
            self.assertEqual(audit_layout(p)['status'], 'PASS')
    def test_margin_violation_detected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'bad.pdf'
            c = canvas.Canvas(str(p), pagesize=(595.2756, 841.8898))
            for i in range(15):
                c.drawString(5 if i==0 else 75, 700-i*15, 'Evidence report content line %d' % i)
            c.save()
            self.assertEqual(audit_layout(p)['status'], 'REVIEW')

    def test_appendix_page_uses_its_declared_top_allowance(self):
        from chronoseal.report_quality import audit_layout
        MM = 72 / 25.4
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'appendix.pdf'
            c = canvas.Canvas(str(p), pagesize=(595.2756, 841.8898))
            # Appendix title sits above the body frame; its word top is ~12mm.
            c.drawString(75, 841.8898 - 16*MM, 'WHOLE FILE TEXT CHECKSUMS')
            for i in range(15):
                c.drawString(75, 700-i*15, 'Checksum appendix content line %d' % i)
            c.save()
            result = audit_layout(p)
            self.assertEqual(result['status'], 'PASS', result['issues'])
            self.assertTrue(result['pages'][0]['appendix'])

    def test_same_position_without_appendix_title_is_reviewed(self):
        from chronoseal.report_quality import audit_layout
        MM = 72 / 25.4
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/'not_appendix.pdf'
            c = canvas.Canvas(str(p), pagesize=(595.2756, 841.8898))
            c.drawString(75, 841.8898 - 16*MM, 'Ordinary body heading above the frame')
            for i in range(15):
                c.drawString(75, 700-i*15, 'Evidence report content line %d' % i)
            c.save()
            result = audit_layout(p)
            self.assertEqual(result['status'], 'REVIEW')
            self.assertFalse(result['pages'][0]['appendix'])


if __name__ == '__main__': unittest.main()
