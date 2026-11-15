import unittest
from unittest.mock import patch
from chronoseal.provider_bootstrap import bootstrap_providers, BootstrapError

class ProviderBootstrapTests(unittest.TestCase):
 def test_existing_validated_trust_is_preserved_without_network(self):
  cfg={'rfc3161':{'start':[{'name':'A','trust_root_files':['a.pem'],'trust_chain_validated':True}],'stop':[{'name':'B','trust_root_files':['b.pem'],'trust_chain_validated':True}]}}
  report,out=bootstrap_providers('.',cfg,'openssl')
  self.assertEqual([x['status'] for x in report['providers']],['EXISTING_VALIDATED','EXISTING_VALIDATED'])
 def test_unqualified_existing_material_is_not_silently_trusted(self):
  cfg={'rfc3161':{'start':[{'name':'A','trust_root_files':['a.pem'],'bootstrap':'bad'}],'stop':[]}}
  with self.assertRaises(BootstrapError): bootstrap_providers('.',cfg,'openssl')
 def test_unknown_bootstrap_blocks(self):
  cfg={'rfc3161':{'start':[{'name':'A','trust_root_files':[],'bootstrap':'bad'}],'stop':[]}}
  with self.assertRaises(BootstrapError):bootstrap_providers('.',cfg,'openssl')
 def test_official_chain_is_classified_and_validated(self):
  cfg={'rfc3161':{'start':[{'name':'A','trust_root_files':[],'bootstrap':'official-download','official_certificate_urls':['x']}],'stop':[]}}
  with patch('chronoseal.provider_bootstrap.bootstrap_official_download',return_value=(['leaf.pem','inter.pem','root.pem'],[])), \
       patch('chronoseal.provider_bootstrap._classify_downloaded',return_value=(['root.pem'],['inter.pem'],['leaf.pem'],[])), \
       patch('chronoseal.provider_bootstrap._validate_chain',return_value='leaf.pem: OK'):
   report,out=bootstrap_providers('.',cfg,'openssl')
  p=out['rfc3161']['start'][0]
  self.assertEqual(p['trust_root_files'],['root.pem']); self.assertEqual(p['intermediate_certificate_files'],['inter.pem']); self.assertEqual(p['embed_certificate_files'],['leaf.pem']); self.assertTrue(p['trust_chain_validated'])
  self.assertEqual(report['providers'][0]['status'],'BOOTSTRAPPED_VALIDATED')
 def test_official_incomplete_chain_uses_windows_recovery(self):
  cfg={'rfc3161':{'start':[{'name':'A','trust_root_files':[],'bootstrap':'official-download','official_certificate_urls':['x']}],'stop':[]}}
  with patch('chronoseal.provider_bootstrap.bootstrap_official_download',return_value=(['leaf.pem'],[])), \
       patch('chronoseal.provider_bootstrap._classify_downloaded',return_value=([],[],['leaf.pem'],[])), \
       patch('chronoseal.provider_bootstrap.os.name','nt'), \
       patch('chronoseal.provider_bootstrap.bootstrap_windows_chain',return_value=(['leaf2.pem','inter2.pem','root2.pem'],[])), \
       patch('chronoseal.provider_bootstrap._x509_meta',return_value={}), \
       patch('chronoseal.provider_bootstrap._validate_chain',return_value='leaf2.pem: OK'):
   _,out=bootstrap_providers('.',cfg,'openssl')
  p=out['rfc3161']['start'][0]; self.assertEqual(p['trust_root_files'],['root2.pem']); self.assertEqual(p['intermediate_certificate_files'],['inter2.pem']); self.assertEqual(p['embed_certificate_files'],['leaf2.pem'])
