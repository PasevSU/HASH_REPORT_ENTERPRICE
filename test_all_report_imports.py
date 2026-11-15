"""Import smoke tests for every report profile entrypoint from foreign cwd."""
import os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SCRIPTS=('hash_report_single.py','hash_report_combined.py','hash_report_core.py','modular_report.py','chronoseal_volume_report.py','hash_report_gui.py','a4_document.py','pdf_object_rules.py')
class AllReportImports(unittest.TestCase):
 def test_direct_imports_from_unrelated_cwd(self):
  for name in SCRIPTS:
   with self.subTest(script=name):
    code=f"import runpy; runpy.run_path({str(ROOT/'hash_report_generator'/name)!r},run_name='__import_smoke__')"
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    r=subprocess.run([sys.executable,'-c',code],cwd=str(ROOT.parent),env=env,capture_output=True,text=True,timeout=30)
    self.assertEqual(r.returncode,0,f'{name}: {r.stderr[-1800:]}')
if __name__=='__main__':unittest.main()
