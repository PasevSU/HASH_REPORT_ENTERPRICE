import sys, unittest, re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pdf_object_rules import combined_column_widths, COLUMNS, validate
from combined_table_layout import timestamp_cell, digest_cell_for_width, safe_text_cell
from reportlab.lib.styles import ParagraphStyle
class LayoutV37(unittest.TestCase):
 def setUp(self): self.style=ParagraphStyle('Test',fontName='Helvetica',fontSize=7,leading=9)
 def test_columns(self):
  widths=combined_column_widths(480)
  self.assertEqual(len(widths),7);self.assertAlmostEqual(sum(widths),480);self.assertGreater(widths[6],widths[2]);self.assertTrue(validate())
 def test_timestamp(self):
  text=timestamp_cell('2026-10-08 14:31:47.705',self.style).text
  self.assertIn('<br/>',text);self.assertIn('14:31:47.705',text)
 def test_digest_complete(self):
  raw='0123456789abcdef'*4
  p=digest_cell_for_width(raw,self.style,90)
  self.assertEqual(p.text.replace('<br/>',''),raw.upper())
 def test_escape(self):
  self.assertIn('&amp;',safe_text_cell('A&B.pdf',self.style).text)
if __name__=='__main__': unittest.main()
