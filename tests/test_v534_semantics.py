import os,re,sys,tempfile,threading,unittest
from pathlib import Path
from chronoseal.pipeline import Pipeline

class V534Semantics(unittest.TestCase):
    def cfg(self): return {'tools':{},'generator':{},'rfc3161':{}}
    def test_input_type_selects_mode_not_radio_value(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); f=root/'x.txt'; f.write_text('x')
            self.assertEqual(Pipeline._input_mode(f),'single')
            self.assertEqual(Pipeline._input_mode(root),'combined')
    def test_large_child_stdout_is_drained_without_deadlock(self):
        with tempfile.TemporaryDirectory() as d:
            p=Pipeline(d,self.cfg(),cancel_event=threading.Event())
            code="import sys; [sys.stdout.write('X'*4096+'\\n') for _ in range(512)]; sys.stdout.flush()"
            r=p._run([sys.executable,'-c',code],timeout=15,encoding='utf-8')
            self.assertEqual(r.returncode,0)
    def test_requested_filename_patterns_are_encoded_in_generators(self):
        root=Path(__file__).resolve().parents[1]
        combo=(root/'hash_report_generator'/'hash_report_combined.py').read_text(encoding='utf-8')
        single=(root/'hash_report_generator'/'hash_report_single.py').read_text(encoding='utf-8')
        self.assertIn('_HASHREPORT_TYP_COMBO.pdf',combo)
        self.assertIn('_HASHREPORT_TYP_SINGLE.pdf',single)
