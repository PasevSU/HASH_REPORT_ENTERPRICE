import unittest, tempfile, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class V538Contract(unittest.TestCase):
 def test_bridge_requires_exactly_two(self):
  s=(ROOT/'bridge'/'stamp.mjs').read_text()
  self.assertIn('expected exactly 2 applied timestamps',s)
  self.assertIn("applied[0].stage!=='START'||applied[1].stage!=='STOP'",s)
  self.assertIn('START and STOP RFC3161 tokens must be distinct',s)
 def test_certificate_inventory_is_audited(self):
  s=(ROOT/'bridge'/'stamp.mjs').read_text()
  self.assertIn('certificate_inventory:certInventory',s)
  self.assertIn('unique_certificate_sha256_count',s)
  self.assertIn("if(expectedCertHashes.size===0)",s)
 def test_transactional_publish_contract(self):
  s=(ROOT/'chronoseal'/'pipeline.py').read_text()
  self.assertIn('report-before-rfc3161.UNSEALED.pdf',s)
  self.assertIn("report.unlink()",s)
  self.assertIn('shutil.copy2(sealed,temp)',s)
  self.assertIn('if sha256(temp)!=final_hash',s)
  self.assertIn('os.link(temp,publish_path)',s)
  self.assertLess(s.index('shutil.copy2(sealed,temp)'),s.index('os.link(temp,publish_path)'))
  self.assertLess(s.index('archive_report('),s.index('shutil.copy2(sealed,temp)'))
if __name__=='__main__':unittest.main()
