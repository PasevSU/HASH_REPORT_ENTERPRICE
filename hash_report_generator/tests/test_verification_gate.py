import importlib.util
import tempfile
import unittest
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / 'bridge' / 'verification_gate.py'
spec = importlib.util.spec_from_file_location('verification_gate', TARGET)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class VerificationGateTests(unittest.TestCase):
    def valid(self):
        return {'status':'PASS','input_sha256':'abc','trust_anchors':[{'sha256':'root'}],
                'timestamps':[{'verified':True},{'verified':True}]}
    def test_two_verified_pass(self):
        self.assertEqual(gate.qualify(self.valid(),'abc')['status'],'PASS')
    def test_mismatched_digest_blocked(self):
        self.assertIn('pdf_digest_mismatch',gate.qualify(self.valid(),'other')['errors'])
    def test_missing_timestamp_blocked(self):
        a=self.valid();a['timestamps'].pop();self.assertEqual(gate.qualify(a,'abc')['status'],'BLOCKED')
    def test_false_timestamp_blocked(self):
        a=self.valid();a['timestamps'][0]['verified']=False;self.assertEqual(gate.qualify(a,'abc')['status'],'BLOCKED')
    def test_no_trust_anchor_blocked(self):
        a=self.valid();a['trust_anchors']=[];self.assertEqual(gate.qualify(a,'abc')['status'],'BLOCKED')
    def test_error_status_blocked(self):
        a=self.valid();a['status']='ERROR';self.assertEqual(gate.qualify(a,'abc')['status'],'BLOCKED')
    def test_sha256_file(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x';p.write_bytes(b'abc');self.assertEqual(gate.sha256_file(p),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
