import io
import tempfile
import unittest
from pathlib import Path
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from chronoseal.page_identity import apply_footer

class A4ProvenanceTests(unittest.TestCase):
    def test_sixth_page_non_a4_rejected_with_coordinates(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'six.pdf'; dst=Path(td)/'output.pdf'
            w=PdfWriter()
            for i in range(6):
                w.add_blank_page(width=595.275590551, height=841.88976378 if i<5 else 792)
            with src.open('wb') as f:w.write(f)
            with self.assertRaisesRegex(ValueError, 'Page 6: not canonical A4') as caught:
                apply_footer(src,dst,'TEST','TEST')
            self.assertIn('actual=',str(caught.exception))
            self.assertIn('CropBox=',str(caught.exception))
            self.assertFalse(dst.exists())
            self.assertEqual(len(PdfReader(str(src)).pages),6)

if __name__=='__main__':unittest.main()
