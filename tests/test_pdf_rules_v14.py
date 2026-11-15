import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hash_report_generator"))
from pdf_object_rules import (validate_rendering_contract, heading_style, legal_paragraph_style, canonical_size, css_text, aligned_fields)
class RulesV14(unittest.TestCase):
    def test_contract(self): self.assertTrue(validate_rendering_contract())
    def test_sizes(self):
        self.assertEqual(canonical_size(1024), "1 024 bytes")
        self.assertRaises(ValueError, canonical_size, -1)
    def test_hierarchy(self):
        self.assertEqual(heading_style("h1").fontSize, 20)
        self.assertEqual(heading_style("h2").fontSize, 14)
        self.assertEqual(heading_style("h3").fontSize, 11)
        self.assertLess(legal_paragraph_style().fontSize, 9)
    def test_css(self):
        css=css_text()
        self.assertIn(".legal-note",css)
        self.assertIn("h1 {",css)
    def test_alignment(self):
        from reportlab.lib.styles import getSampleStyleSheet
        story=[]
        table=aligned_fields(story,[("File Size", "1 024 bytes"),("Report ID","ABC")],getSampleStyleSheet()["Normal"],450)
        self.assertEqual(len(story),1)
        self.assertAlmostEqual(sum(table._colWidths),450)
if __name__ == "__main__": unittest.main()
