import tempfile, unittest
from pathlib import Path
from reportlab.pdfgen import canvas
from chronoseal.assembly_validation import validate_pdf
from chronoseal.report_quality import audit_layout

class TestRedundantValidation(unittest.TestCase):
    def test_three_probes_valid_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"valid.pdf"
            c=canvas.Canvas(str(p));c.drawString(90,700,"valid report");c.showPage();c.save()
            a=validate_pdf(p, expected_pages=1)
            self.assertEqual(a['status'],'PASS')
            self.assertEqual(len(a['checks']),3)
    def test_expected_page_count_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"valid.pdf"
            c=canvas.Canvas(str(p));c.drawString(90,700,"valid report");c.showPage();c.save()
            self.assertEqual(validate_pdf(p,expected_pages=2)['status'],'FAILED')
    def test_corrupt_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.pdf";p.write_bytes(b'not a PDF')
            self.assertEqual(validate_pdf(p)['status'],'FAILED')
    def test_blank_pdf_rejected_by_layout(self):
        import fitz
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"blank.pdf"
            d=fitz.open();d.new_page(width=595.276,height=841.89);d.save(p);d.close()
            result=audit_layout(p)
            self.assertEqual(result['status'],'REVIEW')
            self.assertTrue(any('no extractable text' in x for x in result['issues']))
            self.assertEqual(len(result['pages'][0]['content_probes']),3)
