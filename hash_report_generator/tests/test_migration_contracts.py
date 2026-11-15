import unittest, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from hash_report_generator.module_loader import load_profiles
from hash_report_generator.hash_table_engine import collect_files, build_rows

class MigrationContracts(unittest.TestCase):
    def test_four_required_profiles(self):
        p=load_profiles()
        self.assertEqual({k:p[k]['input_scope'] for k in ('single','single_pdf','combo','combo_all')},
          {'single':'single_file','single_pdf':'single_file','combo':'current_folder','combo_all':'recursive_folder'})
    def test_enumeration_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'nested').mkdir()
            (root/'a.txt').write_bytes(b'a'); (root/'nested'/'b.txt').write_bytes(b'b')
            _, current=collect_files(root,'current_folder')
            _, recursive=collect_files(root,'recursive_folder')
            self.assertEqual([p.name for p in current],['a.txt'])
            self.assertEqual({p.name for p in recursive},{'a.txt','b.txt'})
            self.assertEqual(build_rows(root,'recursive_folder')[0]['size_bytes'],1)
    def test_profile_module_references(self):
        from hash_report_generator.module_loader import load_modules
        p=load_profiles(); m=load_modules()
        for k in ('single','single_pdf','combo','combo_all'):
            self.assertTrue(set(p[k]['modules']) <= set(m))
