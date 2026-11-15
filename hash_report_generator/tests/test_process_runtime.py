import json, tempfile, unittest
from pathlib import Path
from hash_report_generator.process_runtime import execute, verify
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.src=self.root/'src';self.src.mkdir();(self.src/'sub').mkdir();(self.src/'a.txt').write_bytes(b'a');(self.src/'sub'/'b.txt').write_bytes(b'b');self.out=self.root/'out'
 def test_fail_closed(self):
  with self.assertRaises(RuntimeError):execute('combo',self.src,self.out)
 def test_scope(self):
  for profile,n in [('combo',1),('combo_all',2)]:
   path=execute(profile,self.src,self.out,allow_unsealed=True)
   rows=json.loads((path/'hash_table.json').read_text())
   self.assertEqual(rows['count'],n)
   self.assertEqual(verify(path)['artifacts_integrity'],'PASS')
   self.assertEqual(verify(path)['enterprise_release'],'BLOCKED')
 def test_tamper(self):
  path=execute('single',self.src/'a.txt',self.out,allow_unsealed=True)
  (path/'hash_table.json').write_text('{}')
  self.assertEqual(verify(path)['artifacts_integrity'],'FAILED')
 def test_output_inside_input_rejected(self):
  with self.assertRaises(ValueError):execute('combo',self.src,self.src/'reports',allow_unsealed=True)

 def test_evidence_commitment(self):
  path=execute('single',self.src/'a.txt',self.out,allow_unsealed=True)
  self.assertEqual(verify(path)['evidence_commitment'],'PASS')
  manifest=json.loads((path/'manifest.json').read_text())
  manifest['artifacts'][0]['sha256']='0'*64
  (path/'manifest.json').write_text(json.dumps(manifest))
  self.assertEqual(verify(path)['evidence_commitment'],'FAILED')
 def test_unsafe_module_identifier(self):
  modules=self.root/'modules';modules.mkdir()
  (modules/'bad.json').write_text(json.dumps({'id':'../escape','title':'Bad','type':'text'}))
  profiles=self.root/'profiles';profiles.mkdir()
  (profiles/'test.json').write_text(json.dumps({'id':'test','modules':['../escape'],'input_scope':'single_file'}))
  with self.assertRaises(ValueError):execute('test',self.src/'a.txt',self.out,modules_dir=modules,profiles_dir=profiles,allow_unsealed=True)
 def test_unsealed_not_enterprise(self):
  path=execute('single',self.src/'a.txt',self.out,allow_unsealed=True)
  result=verify(path)
  self.assertTrue(result['process_complete'])
  self.assertEqual(result['rfc3161'],'NOT_VERIFIED')
  self.assertEqual(result['enterprise_release'],'BLOCKED')
