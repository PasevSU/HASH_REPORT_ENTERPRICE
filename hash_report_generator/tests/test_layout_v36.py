import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class LayoutV36Tests(unittest.TestCase):
 def test_summary_keep_together(self):
  s=(ROOT/'hash_report_generator/hash_report_core.py').read_text(encoding='utf-8')
  self.assertIn('keep_short_section(',s)
  self.assertNotIn('CondPageBreak(155)',s)
 def test_policy(self):
  from hash_report_generator.style_loader import load_styles
  p=load_styles()['PAGINATION']
  self.assertEqual(p['paper'],'A4')
  self.assertFalse(p['stretch_tables_to_fill_page'])
  self.assertTrue(p['short_tables_keep_together'])
if __name__=='__main__': unittest.main()
