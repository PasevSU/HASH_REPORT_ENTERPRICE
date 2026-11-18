import logging, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from hash_report_generator.a4_document import A4DocTemplate
from hash_report_generator.hash_report_core import ReportConstants
from hash_report_generator.pdf_object_rules import PAGE
from hash_report_generator.hash_report_single import SingleReportGenerator
from chronoseal.page_identity import apply_footer

class FooterPaginationTests(unittest.TestCase):
    def test_canonical_body_clears_footer_collision_boundary(self):
        from hash_report_generator.style_loader import load_styles
        boundary=load_styles()['PAGE_IDENTITY']['collision_boundary_from_bottom_pt']
        self.assertGreater(PAGE['bottom_mm']*mm, boundary)
        self.assertAlmostEqual(ReportConstants.PAGE_MARGIN_BOTTOM, PAGE['bottom_mm']*mm)

    def test_long_report_paginates_without_footer_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'source.pdf'; dst=Path(tmp)/'stamped.pdf'
            doc=A4DocTemplate(str(src))
            story=[Paragraph('Evidence line '+str(i)+' '+('abc '*24),getSampleStyleSheet()['Normal']) for i in range(160)]
            doc.build(story)
            import fitz
            with fitz.open(src) as pdf: self.assertGreater(len(pdf),1)
            manifest=apply_footer(src,dst,'RPT-TEST','DEV')
            self.assertGreater(len(manifest),1)
            with fitz.open(dst) as pdf:
                self.assertEqual(len(pdf),len(manifest))
                for page in pdf: self.assertAlmostEqual(page.rect.width,210*mm,places=1)

    def test_collision_is_not_silently_bypassed(self):
        from reportlab.pdfgen import canvas
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'bad.pdf';dst=Path(tmp)/'out.pdf'
            c=canvas.Canvas(str(src),pagesize=(210*mm,297*mm))
            c.drawString(50,50,'IMPORTANT ORIGINAL CONTENT');c.save()
            with self.assertRaisesRegex(ValueError,'colliding_words='):
                apply_footer(src,dst,'RPT-TEST','DEV')

    def test_single_report_paginates_inside_reserved_footer_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'input.txt'
            source.write_text('footer pagination regression', encoding='utf-8')
            report = root / 'report.pdf'
            stamped = root / 'stamped.pdf'
            with patch.dict(os.environ, {
                'CHRONOSEAL_REPORT_ONLY': '1',
                'CHRONOSEAL_INCLUDE_EXPLANATION': '0',
            }):
                generator = SingleReportGenerator(logging.getLogger('footer-pagination-test'))
                file_info = generator.get_file_info(source)
                self.assertIsNotNone(file_info)
                self.assertTrue(generator.generate(file_info, str(report)))
            manifest = apply_footer(report, stamped, 'RPT-TEST', 'DEV')
            import fitz
            with fitz.open(stamped) as pdf:
                self.assertEqual(len(pdf), len(manifest))
