import importlib.util, tempfile, unittest, sys, logging
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RecursionSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(ROOT/'hash_report_generator'))
        spec=importlib.util.spec_from_file_location('combined', ROOT/'hash_report_generator'/'hash_report_combined.py')
        cls.m=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.m)
    def test_combined_default_is_current_folder_only(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); (r/'top.txt').write_text('top'); (r/'nested').mkdir(); (r/'nested'/'deep.txt').write_text('deep')
            g=self.m.CombinedReportGenerator(logging.getLogger("test"), include_ots=False)
            names={x['name'] for x in g._discover_all_files_from_folder(r,recursive=False)}
            self.assertIn('top.txt',names); self.assertNotIn('nested/deep.txt',names)
    def test_recursive_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); (r/'top.txt').write_text('top'); (r/'nested').mkdir(); (r/'nested'/'deep.txt').write_text('deep')
            g=self.m.CombinedReportGenerator(logging.getLogger("test"), include_ots=False)
            names={x['name'] for x in g._discover_all_files_from_folder(r,recursive=True)}
            self.assertIn('top.txt',names); self.assertIn('nested/deep.txt',names)
if __name__=='__main__': unittest.main()
