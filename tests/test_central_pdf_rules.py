import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'hash_report_generator'))
sys.path.insert(0,str(ROOT))
from pdf_object_rules import validate,content_width_mm,OBJECTS,COLUMNS,css_text
from chronoseal.unified_theme import report_style
class CentralRulesTests(unittest.TestCase):
    def test_width(self): self.assertGreater(content_width_mm(),160);self.assertLessEqual(content_width_mm(),170)
    def test_all_objects(self): self.assertGreaterEqual(len(OBJECTS),25);self.assertTrue(validate())
    def test_all_modes(self):
        for k in ('single','combo','combo_all','single_pdf','volume','automation','verification'): self.assertTrue(report_style(k)['same_visual_language'])
    def test_css_header_contrast(self): self.assertIn('!important',css_text())
    def test_columns(self): self.assertAlmostEqual(sum(COLUMNS['combined'].values()),1)
if __name__=='__main__':unittest.main()
