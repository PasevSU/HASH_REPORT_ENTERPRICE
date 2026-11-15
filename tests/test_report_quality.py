import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chronoseal.report_quality import audit_layout
class TestReportQuality(unittest.TestCase):
    def test_blank_a4_detected(self):
        import fitz, tempfile
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'blank.pdf'
            d=fitz.open();d.new_page(width=595.276,height=841.89);d.save(path);d.close()
            result=audit_layout(path)
            self.assertEqual(result['status'],'REVIEW')
            self.assertTrue(any('no extractable text' in x for x in result['issues']))
if __name__=='__main__': unittest.main()
