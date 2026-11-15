import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reportlab.platypus import Paragraph,Table,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet
from pagination_policy import keep_short_section,pagination_config
class PaginationPolicyTests(unittest.TestCase):
    def test_central_config(self):
        self.assertEqual(pagination_config()['section_break_strategy'],'measure_flowables')
    def test_short_section_kept(self):
        p=Paragraph('Heading',getSampleStyleSheet()['Normal'])
        t=Table([['a','b'],['c','d']])
        self.assertIsInstance(keep_short_section(p,t),KeepTogether)
    def test_long_section_not_forced(self):
        p=Paragraph('Heading',getSampleStyleSheet()['Normal'])
        t=Table([[str(i)] for i in range(20)])
        with self.assertRaises(ValueError):keep_short_section(p,t)
if __name__=='__main__':unittest.main()
