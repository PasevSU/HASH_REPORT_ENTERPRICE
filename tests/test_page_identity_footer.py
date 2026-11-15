import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas
from pypdf import PdfReader

from chronoseal.page_identity import apply_footer

MM = 72 / 25.4
A4 = (595.275590551, 841.88976378)
SAFE_EDGE_MM = 5.0


def _body_pdf(path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont('Helvetica', 11)
    for i in range(15):
        c.drawString(60, 700 - i * 18, 'Evidence body line %d for footer geometry' % i)
    c.save()
    return path


def _footer_words(page):
    import fitz
    from chronoseal.unified_report_profile import DEFAULT_PROFILE as profile
    limit = page.rect.height - profile.footer_band_mm * MM
    return [w for w in page.get_text('words') if w[1] >= limit]


class FooterGeometryTests(unittest.TestCase):
    def test_footer_clears_paper_edges(self):
        import fitz
        with tempfile.TemporaryDirectory() as td:
            src = _body_pdf(Path(td) / 'body.pdf')
            out = Path(td) / 'out.pdf'
            apply_footer(src, out, 'RPT-TEST-0001', 'TEST')
            with fitz.open(out) as doc:
                page = doc[0]
                words = _footer_words(page)
                self.assertTrue(words)
                self.assertGreaterEqual(min(w[0] for w in words) / MM, SAFE_EDGE_MM - 0.05)
                self.assertLessEqual(max(w[2] for w in words) / MM, page.rect.width / MM - SAFE_EDGE_MM + 0.05)
                self.assertGreaterEqual((page.rect.height - max(w[3] for w in words)) / MM, SAFE_EDGE_MM - 0.05)

    def test_footer_words_do_not_overlap(self):
        import fitz
        with tempfile.TemporaryDirectory() as td:
            src = _body_pdf(Path(td) / 'body.pdf')
            out = Path(td) / 'out.pdf'
            apply_footer(src, out, 'RPT-TEST-0002', 'TEST')
            with fitz.open(out) as doc:
                words = _footer_words(doc[0])
                for i, a in enumerate(words):
                    for b in words[i + 1:]:
                        overlap = (a[0] < b[2] - 0.5 and b[0] < a[2] - 0.5
                                   and a[1] < b[3] - 0.5 and b[1] < a[3] - 0.5)
                        self.assertFalse(overlap, 'footer words overlap: %r / %r' % (a[4], b[4]))

    def test_recomposing_an_already_footered_pdf_keeps_one_footer(self):
        import fitz
        with tempfile.TemporaryDirectory() as td:
            src = _body_pdf(Path(td) / 'body.pdf')
            first = Path(td) / 'first.pdf'
            second = Path(td) / 'second.pdf'
            apply_footer(src, first, 'RPT-TEST-0003', 'TEST')
            # The generated appendix page is preserved, not re-furnished; a fresh
            # appendix page is still appended for the new composition.
            appendix_index = len(PdfReader(str(first)).pages) - 1
            apply_footer(first, second, 'RPT-TEST-0003', 'TEST', preserve_pages={appendix_index})
            self.assertEqual(len(PdfReader(str(second)).pages), appendix_index + 2)
            with fitz.open(second) as doc:
                text = doc[0].get_text('text')
                self.assertEqual(text.count('RPT-TEST-0003'), 1)
                self.assertEqual(text.count('PAGE TEXT HASHES'), 1)
                self.assertIn('WHOLE FILE TEXT CHECKSUMS', doc[appendix_index].get_text('text'))


if __name__ == '__main__':
    unittest.main()
