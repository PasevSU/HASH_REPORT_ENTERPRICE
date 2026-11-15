import importlib.util,sys,tempfile,unittest,json
from pathlib import Path
BRIDGE=Path(__file__).resolve().parents[2]/'bridge'
sys.path.insert(0,str(BRIDGE))
spec=importlib.util.spec_from_file_location('enterprise_finalization',BRIDGE/'enterprise_finalization.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FinalizationTests(unittest.TestCase):
 def test_verified_immutable(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'input.pdf';p.write_bytes(b'%PDF-1.7\nexample')
   def verifier(pdf,roots,output,**kwargs):
    audit={'schema':'chronoseal.verification-gate/v1','status':'PASS','errors':[],'pdf_sha256':m.digest(pdf),'verified_timestamp_count':2,'minimum_timestamps':2,'library_audit':{'status':'PASS','input_sha256':m.digest(pdf),'timestamps':[{'verified':True},{'verified':True}],'trust_anchors':['approved']}}
    output.write_text(json.dumps(audit))
    return audit
   result=m.finalize('single',p,[Path(td)/'root.pem'],Path(td)/'out',verifier=verifier)
   self.assertEqual(result['status'],'VERIFIED');self.assertEqual(p.read_bytes(),b'%PDF-1.7\nexample')
   self.assertEqual(json.loads((Path(td)/'out'/'finalization.json').read_text())['pdf_modified'],False)
 def test_reject_unknown_profile(self):
  with self.assertRaises(ValueError):m.finalize('volume','missing.pdf',[],'.')
 def test_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.4')
   def verifier(*args,**kwargs):raise RuntimeError('TSA unavailable')
   self.assertEqual(m.finalize('combo',p,[],Path(td)/'out',verifier=verifier)['status'],'BLOCKED')
 def test_mutation_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.4')
   def verifier(pdf,roots,output,**kwargs):
    pdf.write_bytes(b'changed');return {'status':'PASS','errors':[]}
   result=m.finalize('combo_all',p,[],Path(td)/'out',verifier=verifier)
   self.assertEqual(result['status'],'BLOCKED');self.assertIn('pdf_changed_during_finalization',result['errors'])

class AuditBindingTests(unittest.TestCase):
 def test_no_audit_is_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7\n')
   self.assertEqual(m.finalize('single',p,[],Path(td)/'out',verifier=lambda *a,**k:{'status':'PASS','errors':[]})['status'],'BLOCKED')
 def test_wrong_hash_is_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7\n')
   def fake(pdf,roots,out,**kwargs):
    out.write_text(json.dumps({'status':'PASS','pdf_sha256':'0'*64,'verified_timestamp_count':2}))
    return {'status':'PASS','errors':[]}
   self.assertEqual(m.finalize('combo',p,[],Path(td)/'out',verifier=fake)['status'],'BLOCKED')
 def test_one_stamp_is_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7\n')
   def fake(pdf,roots,out,**kwargs):
    out.write_text(json.dumps({'status':'PASS','pdf_sha256':m.digest(pdf),'verified_timestamp_count':1}))
    return {'status':'PASS','errors':[]}
   self.assertEqual(m.finalize('combo_all',p,[],Path(td)/'out',verifier=fake)['status'],'BLOCKED')

class HardenedGateTests(unittest.TestCase):
 def test_forged_count_without_library_evidence_blocked(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7')
   def fake(pdf,roots,out,**kw):
    data={'schema':'chronoseal.verification-gate/v1','status':'PASS','pdf_sha256':m.digest(pdf),'verified_timestamp_count':2,'minimum_timestamps':2,'errors':[]}
    out.write_text(json.dumps(data));return data
   r=m.finalize('single',p,[],Path(td)/'out',verifier=fake)
   self.assertEqual(r['status'],'BLOCKED');self.assertIn('library_evidence_missing_or_unbound',r['errors'])
 def test_output_symlink_to_pdf_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7')
   out=Path(td)/'out';out.mkdir()
   (out/'verification.json').symlink_to(p)
   with self.assertRaises(ValueError):m.finalize('single',p,[],out)
 def test_boolean_count_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x.pdf';p.write_bytes(b'%PDF-1.7')
   def fake(pdf,roots,out,**kw):
    data={'schema':'chronoseal.verification-gate/v1','status':'PASS','pdf_sha256':m.digest(pdf),'verified_timestamp_count':True,'minimum_timestamps':2,'errors':[],'library_audit':{'status':'PASS','input_sha256':m.digest(pdf),'timestamps':[{'verified':True},{'verified':True}],'trust_anchors':['approved']}}
    out.write_text(json.dumps(data));return data
   self.assertEqual(m.finalize('single',p,[],Path(td)/'out',verifier=fake)['status'],'BLOCKED')
