import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from hash_report_generator.module_loader import load_modules,load_profiles
from hash_report_generator.style_loader import load_styles
from hash_report_generator.modular_report import render_report
from unittest.mock import patch
class EnterpriseTests(unittest.TestCase):
 def test_styles(self):
  d=load_styles();self.assertIn('page_footer',d['LAYOUT_OBJECTS']);self.assertIn('file_information',d['PROCESS_BLOCKS'])
 def test_modules(self):
  self.assertIn('file_information',load_modules())
 def test_profiles(self):
  self.assertIn('single_pdf',load_profiles())
  self.assertIn('file_information_report',load_profiles())
 def test_dynamic_discovery(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'nested').mkdir();(root/'nested'/'new.js').write_text('module.exports = '+json.dumps({'id':'new','type':'text','title':'New'})+';');self.assertIn('new',load_modules(root))
 def test_unknown_module_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad.json';p.write_text(json.dumps({'id':'bad','modules':['missing']}))
   with self.assertRaises(ValueError):load_profiles(tmp,load_modules())
 def test_pdf(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'sample.txt';f.write_text('ChronoSeal test',encoding='utf8');out=Path(tmp)/'report.pdf'
   with patch('hash_report_generator.pdf_object_rules.font_name',return_value='Helvetica'):
    render_report('single',out,[f],{'Operator':'QA'},'Demo only')
   self.assertGreater(out.stat().st_size,1000)
 def test_reference_file_information_report(self):
  import fitz
  import hashlib
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'evidence.bin';payload=b'x'*355696;f.write_bytes(payload);out=Path(tmp)/'file-information.pdf'
   render_report('file_information_report',out,[f],{'Hardware ID':'HW-TEST','Report ID':'RPT-TEST-1234'})
   with fitz.open(out) as pdf:
    text='\n'.join(page.get_text() for page in pdf)
    self.assertAlmostEqual(pdf[0].rect.width,595.276,delta=0.1)
    self.assertAlmostEqual(pdf[0].rect.height,841.890,delta=0.1)
    self.assertTrue(pdf[0].get_images(full=True))
   normalized=' '.join(text.split())
   for expected in ('FILE INFORMATION:', 'Property', 'Value', 'File Name', 'evidence.bin',
                    '347.359 KB', 'Created', 'Last Modified', 'SHA-256 Hash',
                    'HW-TEST', 'RPT-TEST-1234',
                    'RFC 3161/5816', 'keine eidesstattliche Versicherung'):
    self.assertIn(expected,normalized)
   self.assertIn(hashlib.sha256(payload).hexdigest(),normalized.replace(' ', ''))
   from chronoseal.report_quality import audit_layout
   audit=audit_layout(out)
   self.assertEqual(audit['status'],'PASS',audit)
   with self.assertRaisesRegex(ValueError,'cannot overwrite its source file'):
    render_report('file_information_report',f,[f])
   self.assertEqual(f.read_bytes(),payload)
if __name__=='__main__':unittest.main()
