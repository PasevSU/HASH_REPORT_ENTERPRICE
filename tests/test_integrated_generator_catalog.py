import unittest,tempfile,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from chronoseal.pipeline import Pipeline
from chronoseal.provider_catalog import apply_profile
class T(unittest.TestCase):
 def cfg(self):return json.loads((ROOT/'config/config.json').read_text(encoding='utf-8'))
 def test_integrated_generator_discovery_combined(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(Pipeline(ROOT,self.cfg()).discover_generator(td,'combined').resolve(),(ROOT/'hash_report_generator/hash_report_combined.py').resolve())
 def test_integrated_generator_discovery_single(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(Pipeline(ROOT,self.cfg()).discover_generator(td,'single').resolve(),(ROOT/'hash_report_generator/hash_report_single.py').resolve())
 def test_catalog_freetsa(self):
  c=self.cfg();apply_profile(c,'start','FreeTSA');self.assertEqual(c['rfc3161']['start'][0]['url'],'https://freetsa.org/tsr')
 def test_catalog_qtsa_free(self):
  c=self.cfg();apply_profile(c,'start','QTSA-Free-Standard');self.assertEqual(c['rfc3161']['start'][0]['url'],'https://ca.signfiles.com/TSAServer.aspx')
 def test_catalog_btrust_published_service_address_and_unconfirmed_access(self):
  c=self.cfg();apply_profile(c,'stop','B-Trust-QTSA');p=c['rfc3161']['stop'][0]
  self.assertTrue(c['rfc3161']['require_qualified_stop']);self.assertTrue(p['qualified'])
  self.assertEqual(p['url'],'http://tsa.b-trust.org')
  self.assertFalse(p['service_access_confirmed'])
  self.assertEqual(p['policy_oid'],'0.4.0.2023.1.1')
  self.assertEqual(p['trusted_list_service_status'],'granted')
  self.assertEqual(p['trusted_list_service_certificate_file'],'trust\\B-Trust\\qualified-tsa-service.pem')
  self.assertEqual(p['trust_root_files'],[])
 def test_catalog_infonotary_qualified_profile_and_ca_identity(self):
  c=self.cfg();apply_profile(c,'stop','InfoNotary-QTSA');p=c['rfc3161']['stop'][0]
  self.assertTrue(c['rfc3161']['require_qualified_stop']);self.assertTrue(p['qualified'])
  self.assertEqual(p['url'],'http://ts.infonotary.com/tsa')
  self.assertEqual(p['policy_oid'],'1.3.6.1.4.1.22144.3.4.1')
  self.assertEqual(p['trusted_list_service_certificate_sha256'],'A4527BA3CDB627494FAC2F58069B37969A3219CF9154B324314A5C97701BDFBF')
  self.assertTrue(p['service_access_confirmed'])
  self.assertEqual(p['intermediate_certificate_files'],['trust\\InfoNotary\\qualified-timestamp-ca.pem'])
  self.assertEqual(p['trusted_list_service_name'],'InfoNotary Qualified TimeStamping Service CA')
 def test_standard_stop_profile_does_not_disable_qualified_requirement(self):
  c=self.cfg();c['rfc3161']['require_qualified_stop']=True
  apply_profile(c,'stop','DigiCert')
  self.assertTrue(c['rfc3161']['require_qualified_stop'])
 def test_aloaha_proxy_not_raw_profile(self):
  with self.assertRaises(ValueError):apply_profile(self.cfg(),'start','Aloaha-External-Proxy')
if __name__=='__main__':unittest.main()

class TrustSeparation(unittest.TestCase):
 def test_bridge_does_not_promote_leaf_to_trust_anchor(self):
  s=(ROOT/'bridge/stamp.mjs').read_text(encoding='utf-8')
  store=s.split('async function store(provider)',1)[1].split('async function verifyOne',1)[0]
  self.assertIn('trust_root_files',store)
  self.assertIn('trusted_list_service_certificate_file',store)
  self.assertNotIn('embed_certificate_files',store)
  self.assertNotIn('intermediate_certificate_files',store)

class AloahaProjectScope(unittest.TestCase):
 def cfg(self):return json.loads((ROOT/'config/config.json').read_text(encoding='utf-8'))
 def test_native_aloaha_is_raw_rfc3161_but_nonqualified_and_manual_trust(self):
  c=self.cfg(); x=c['provider_catalog']['Aloaha-CodeB-InHouse']
  self.assertEqual(x['protocol'],'rfc3161-raw'); self.assertFalse(x['qualified'])
  self.assertEqual(x['bootstrap'],'manual-pin'); self.assertEqual(x['auth'],'none')
  self.assertEqual(x['hashes'],['SHA-256','SHA-384','SHA-512'])
  apply_profile(c,'start','Aloaha-CodeB-InHouse')
  p=c['rfc3161']['start'][0]; self.assertEqual(p['bootstrap'],'manual-pin'); self.assertFalse(p['qualified'])
 def test_aloaha_proxy_requires_adapter_and_sha256(self):
  c=self.cfg(); x=c['provider_catalog']['Aloaha-External-Proxy']
  self.assertEqual(x['adapter'],'aloaha_timestamp_proxy'); self.assertEqual(x['hashes'],['SHA-256'])
  with self.assertRaises(ValueError): apply_profile(c,'start','Aloaha-External-Proxy')
 def test_aloaha_ocsp_capability_is_project_scoped(self):
  x=self.cfg()['provider_catalog']['Aloaha-CodeB-InHouse']
  self.assertEqual(x['ocsp_url_template'],'https://<tenant-host>/csc/v2/ocsp')
