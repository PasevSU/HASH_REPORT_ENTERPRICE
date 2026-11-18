import tempfile, unittest, subprocess, json, shutil, os, base64, hashlib, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chronoseal.settings import executable

# Use the product's own resolver: Windows installations often keep OpenSSL off
# PATH (the app has a Program Files fallback), and a PATH-only skip silently
# disabled every security contract test on such a machine.
NODE = executable('node')
OPENSSL = executable('openssl')

# v5.11.0 - de-flake: an RSA-2048 keypair per provider was generated for every
# single test case, i.e. 16 key generations per run. On a network share that is
# slow enough that the Node child process could hit the 20 s wall clock and the
# suite reported a false failure. The roots are now created once per process and
# copied into each fixture, and the Node timeout is contention-tolerant.
_NODE_TIMEOUT = 120
_ROOT_CACHE = {}

def _cached_root(name):
    """Return (key_bytes, pem_bytes) for Root <NAME>, generating at most once."""
    if not OPENSSL:
        return None
    hit = _ROOT_CACHE.get(name)
    if hit is None:
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td:
            td = Path(td)
            subprocess.run([OPENSSL, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-subj', f'/CN={name.upper()} Test Root',
                            '-keyout', str(td / 'k.pem'), '-out', str(td / 'c.pem'),
                            '-days', '2'], check=True, capture_output=True)
            hit = ((td / 'k.pem').read_bytes(), (td / 'c.pem').read_bytes())
        _ROOT_CACHE[name] = hit
    return hit

def fake_openssl(root):
    if os.name=='nt':
        p=root/'fake-openssl.cmd'; p.write_text('@echo Verification: OK\r\n',encoding='utf-8')
    else:
        p=root/'fake-openssl'; p.write_text('#!/bin/sh\necho "Verification: OK"\n',encoding='utf-8'); p.chmod(0o755)
    return str(p)

def pdf_revision(tag='AA'):
    # Structurally sufficient deterministic mock revision for the bridge's independent parser.
    # ByteRange selects the first 4 bytes + zero bytes; fake OpenSSL is the crypto oracle in these contract tests.
    return f"\n10 0 obj << /Type /DocTimeStamp /SubFilter /ETSI.RFC3161 /ByteRange [0 4 4 0] /Contents <{tag}00> >> endobj\n/DSS << /Certs [] >>\n|TS|".encode()

@unittest.skipUnless(NODE and OPENSSL,'node and openssl required')
class BridgeContract(unittest.TestCase):
 def setup_case(self,d, extractor_mode='normal', bad_structure=False):
   r=Path(d); (r/'bridge').mkdir(); shutil.copy2(ROOT/'bridge'/'stamp.mjs',r/'bridge'/'stamp.mjs')
   # A real npm project has package.json next to node_modules; Node's ESM package
   # scope lookup stops there instead of walking up into the user profile.
   (r/'package.json').write_text('{"name":"chronoseal-bridge-fixture","private":true,"type":"module"}')
   nm=r/'node_modules'/'pdf-rfc3161'; nm.mkdir(parents=True); (nm/'package.json').write_text('{"name":"pdf-rfc3161","version":"0.2.0","type":"module","exports":"./index.js"}')
   # Use real X.509 DER in the mock DSS so the production physical-certificate gate is exercised.
   for name in ('a','b'):
    key,pem=_cached_root(name)
    (r/f'{name}.key').write_bytes(key)
    (r/f'{name}.pem').write_bytes(pem)
   if extractor_mode=='zero': extract="export async function extractTimestamps(){return []}"
   elif extractor_mode=='throw': extract="export async function extractTimestamps(){throw Error('extractor synthetic failure')}"
   else: extract="export async function extractTimestamps(pdf){let s=new TextDecoder('latin1').decode(pdf),n=(s.match(/\\|TS\\|/g)||[]).length;return Array.from({length:n},(_,i)=>({info:{genTime:'T',policy:'1.2.3'},i}))}"
   if bad_structure:
    ts_impl="let rv=new TextEncoder().encode('/DSS /Certs |TS|');let a=[...pdf,...rv]"
   else:
    ts_impl="""let s=new TextDecoder('latin1').decode(pdf),n=(s.match(/\\|TS\\|/g)||[]).length,tag=n?'BB':'AA',obj=n?21:20,refs=n?'20 0 R 21 0 R':'20 0 R';let cert=revocationData.certificates[0];let pre=new TextEncoder().encode(`\n${obj} 0 obj << /Length ${cert.length} >>\nstream\n`),post=new TextEncoder().encode(`\nendstream\nendobj\n30 0 obj << /Type /DSS /Certs [ ${refs} ] >> endobj\n10 0 obj << /Type /DocTimeStamp /SubFilter /ETSI.RFC3161 /ByteRange [0 4 4 0] /Contents <${tag}00> >> endobj\n|TS|`);let a=[...pdf,...pre,...cert,...post]"""
   (nm/'index.js').write_text(f"""export class SimpleTrustStore{{addCertificate(x){{}}}}
{extract}
export async function timestampPdf({{pdf,revocationData,tsa}}){{{ts_impl};return {{pdf:new Uint8Array(a),timestamp:{{genTime:'2026-01-01T00:00:00Z'}},ltvData:{{certificates:revocationData.certificates,ocspResponses:[],crls:[]}}}}}}
export async function verifyTimestamp(ts){{return {{...ts,verified:true,info:ts.info}}}}
""")
   inp=r/'in.pdf'; inp.write_bytes(b'%PDF-1.4\n')
   op=fake_openssl(r)
   cfg={'tools':{'openssl':op},'rfc3161':{'mode':'DUAL-STAMP','hash_algorithm':'SHA-512','enable_ltv':True,'strict_ess':True,'require_distinct_providers':True,'start':[{'name':'A','url':'https://a.invalid','trust_root_files':['a.pem']}],'stop':[{'name':'B','url':'https://b.invalid','trust_root_files':['b.pem']}]}}
   (r/'config').mkdir(); (r/'config'/'config.json').write_text(json.dumps(cfg)); return r,inp
 def run_case(self,r,inp):
   out=r/'out.pdf';audit=r/'audit.json';p=subprocess.run([NODE,str(r/'bridge'/'stamp.mjs'),'--input',str(inp),'--output',str(out),'--policy',str(r/'config'/'config.json'),'--audit',str(audit),'--evidence',str(r/'evidence')],cwd=r,capture_output=True,text=True,timeout=_NODE_TIMEOUT);return p,out,audit
 def test_dual_stamp_reopen_reverify_audit(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);p,out,audit=self.run_case(r,inp);self.assertEqual(p.returncode,0,p.stderr);a=json.loads(audit.read_text());self.assertEqual(a['status'],'PASS');self.assertTrue(a['final_reverification']['verified']);self.assertEqual(a['final_reverification']['count'],2);self.assertEqual(out.read_bytes().count(b'/Type /DocTimeStamp'),2);self.assertEqual(a['verification_paths']['openssl_rfc3161'],'MANDATORY')
 def test_extractor_zero_blocks_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d,'zero');p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('mandatory semantic verification impossible',p.stderr);self.assertFalse(audit.exists())
 def test_extractor_exception_blocks_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d,'throw');p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('synthetic failure',p.stderr);self.assertIn('mandatory semantic verification impossible',p.stderr)
 def test_semantic_verification_failure_blocks_despite_openssl_ok(self):
  with tempfile.TemporaryDirectory() as d:
    r,inp=self.setup_case(d);m=r/'node_modules'/'pdf-rfc3161'/'index.js';m.write_text(m.read_text().replace("export async function verifyTimestamp(ts){return {...ts,verified:true,info:ts.info}}","export async function verifyTimestamp(ts){return {...ts,verified:false,info:ts.info}}"));p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('verification failed',p.stderr)
 def test_semantic_options_are_passed_to_every_verification(self):
  with tempfile.TemporaryDirectory() as d:
    r,inp=self.setup_case(d);m=r/'node_modules'/'pdf-rfc3161'/'index.js';m.write_text(m.read_text().replace("export async function verifyTimestamp(ts){return {...ts,verified:true,info:ts.info}}","export async function verifyTimestamp(ts,o){if(o.strictESSValidation!==true||o.requireTimestampingEKU!==true||o.requireCertValidAtGenTime!==true)throw Error('semantic options missing');return {...ts,verified:true,info:ts.info}}"));p,out,audit=self.run_case(r,inp);self.assertEqual(p.returncode,0,p.stderr)
 def test_distinct_provider_requires_distinct_name_and_endpoint(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);c=r/'config'/'config.json';cfg=json.loads(c.read_text());cfg['rfc3161']['stop'][0]['url']=cfg['rfc3161']['start'][0]['url'];c.write_text(json.dumps(cfg));p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('no distinct STOP provider',p.stderr)
 def test_identical_signer_certificate_across_providers_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);c=r/'config'/'config.json';cfg=json.loads(c.read_text());shutil.copy2(r/'a.pem',r/'signer_a.pem');shutil.copy2(r/'a.pem',r/'signer_b.pem')
   cfg['rfc3161']['start'][0]['embed_certificate_files']=['signer_a.pem'];cfg['rfc3161']['stop'][0]['embed_certificate_files']=['signer_b.pem'];c.write_text(json.dumps(cfg));p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('no distinct STOP provider',p.stderr)
 def test_shared_root_with_different_signer_leaves_is_accepted(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);c=r/'config'/'config.json';cfg=json.loads(c.read_text());shutil.copy2(r/'a.pem',r/'root.pem')
   cfg['rfc3161']['start'][0]['trust_root_files']=['root.pem'];cfg['rfc3161']['stop'][0]['trust_root_files']=['root.pem'];cfg['rfc3161']['start'][0]['embed_certificate_files']=['a.pem'];cfg['rfc3161']['stop'][0]['embed_certificate_files']=['b.pem'];c.write_text(json.dumps(cfg));p,out,audit=self.run_case(r,inp)
   # The one-certificate mock DSS cannot satisfy physical coverage for multi-cert providers; only distinctness is asserted here.
   self.assertNotIn('no distinct STOP provider',p.stderr);self.assertIn('final physical DSS certificate coverage failed',p.stderr)
 def test_unsigned_pdf_mentioning_byterange_is_not_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);inp.write_bytes(b'%PDF-1.4\n1 0 obj << /Note (documentation of /ByteRange [0 1 2 3]) >> endobj\n');p,out,audit=self.run_case(r,inp);self.assertEqual(p.returncode,0,p.stderr)
 def test_signed_pdf_is_still_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);inp.write_bytes(b'%PDF-1.4\n1 0 obj << /Type /Sig /ByteRange [0 4 4 0] /Contents <AA00> >> endobj\n');p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('INPUT_ALREADY_SIGNED',p.stderr)
 def test_current_config_uses_validated_infonotary_profile(self):
  cfg=json.loads((ROOT/'config'/'config.json').read_text(encoding='utf-8'))
  self.assertTrue(cfg['rfc3161']['require_qualified_stop'])
  self.assertEqual(cfg['rfc3161']['stop'][0]['name'],'InfoNotary-QTSA')
  self.assertTrue(cfg['rfc3161']['stop'][0]['qualified'])
  self.assertEqual(cfg['rfc3161']['stop'][0]['url'],'http://ts.infonotary.com/tsa')
  self.assertTrue(cfg['rfc3161']['stop'][0]['service_access_confirmed'])
  self.assertEqual(cfg['rfc3161']['trusted_list_validation']['lotl_signer_sha256'],
                   'E0A620FBB6747362BB933AC44169D676A553444716CF5F31605F12A22B8396B1')
  self.assertTrue((ROOT/'trust'/'LOTL'/'eu-lotl.xml').is_file())
  self.assertTrue((ROOT/'trust'/'LOTL'/'tsl-bg.xml').is_file())
  self.assertTrue((ROOT/'trust'/'InfoNotary'/'qualified-root.pem').is_file())
  self.assertTrue((ROOT/'trust'/'InfoNotary'/'qualified-timestamp-ca.pem').is_file())
 def test_missing_pdf_structure_blocks_even_if_library_returns_success(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d,bad_structure=True);p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('PDF structural DocTimeStamp invariant failed',p.stderr)
 def test_missing_configured_certificate_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d); nm=r/'node_modules'/'pdf-rfc3161'/'index.js';txt=nm.read_text();txt=txt.replace('certificates:revocationData.certificates','certificates:[]');nm.write_text(txt);p,out,audit=self.run_case(r,inp);self.assertNotEqual(p.returncode,0);self.assertIn('missing from LTV/DSS candidate material',p.stderr)
 def qualified_stop(self,r,required=False):
  cfg_path=r/'config'/'config.json';cfg=json.loads(cfg_path.read_text());cert=re.search(r'-----BEGIN CERTIFICATE-----([\s\S]+?)-----END CERTIFICATE-----',(r/'b.pem').read_text()).group(1);pin=hashlib.sha256(base64.b64decode(re.sub(r'\s+','',cert))).hexdigest().upper()
  stop=cfg['rfc3161']['stop'][0];stop.update({'qualified':True,'policy_oid':'1.2.3','trusted_list_service_certificate_sha256':pin,'trusted_list_service_certificate_file':'b.pem','trusted_list_service_status':'granted','trusted_list_service_name':'B test QTSA'})
  cfg['rfc3161']['require_qualified_stop']=required;cfg_path.write_text(json.dumps(cfg));return cfg_path
 def test_qualified_stop_requests_and_verifies_expected_policy(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);self.qualified_stop(r);mod=r/'node_modules'/'pdf-rfc3161'/'index.js';txt=mod.read_text().replace('export async function timestampPdf({pdf,revocationData,tsa}){','export async function timestampPdf({pdf,revocationData,tsa}){if(new TextDecoder().decode(pdf).includes("|TS|")&&tsa.policy!=="1.2.3")throw Error("qualified TSA request policy missing "+JSON.stringify(tsa));');mod.write_text(txt)
   p,out,audit=self.run_case(r,inp);self.assertEqual(p.returncode,0,p.stderr);a=json.loads(audit.read_text());self.assertTrue(a['qualified_stop_profile_selected']);self.assertEqual(a['events'][1]['qualified_provider']['observed_policy_oid'],'1.2.3');self.assertEqual(a['qualified_timestamp_status'],'NOT_ESTABLISHED')
 def test_qualified_stop_rejects_different_returned_policy(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);self.qualified_stop(r);mod=r/'node_modules'/'pdf-rfc3161'/'index.js';mod.write_text(mod.read_text().replace("policy:'1.2.3'","policy:'9.9.9'"));p,out,audit=self.run_case(r,inp)
   self.assertNotEqual(p.returncode,0);self.assertIn('timestamp policy mismatch',p.stderr);self.assertFalse(audit.exists())
 def test_qualified_stop_rejects_unpinned_trust_anchor(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);cfg_path=self.qualified_stop(r);cfg=json.loads(cfg_path.read_text());cfg['rfc3161']['stop'][0]['trusted_list_service_certificate_sha256']='0'*64;cfg_path.write_text(json.dumps(cfg));p,out,audit=self.run_case(r,inp)
   self.assertNotEqual(p.returncode,0);self.assertIn('service identity certificate does not match the Trusted List fingerprint',p.stderr)
 def test_qualified_service_identity_is_not_a_ca_trust_anchor(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);cfg_path=self.qualified_stop(r);cfg=json.loads(cfg_path.read_text());cfg['rfc3161']['stop'][0]['trust_root_files']=[];cfg_path.write_text(json.dumps(cfg));p,out,audit=self.run_case(r,inp)
   self.assertNotEqual(p.returncode,0);self.assertIn('no CA trust anchor configured',p.stderr)
 def test_required_qualified_stop_blocks_until_qualification_validation_exists(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);self.qualified_stop(r,required=True);p,out,audit=self.run_case(r,inp)
   self.assertNotEqual(p.returncode,0);self.assertIn('trusted-list validation is not provisioned',p.stderr);self.assertFalse(out.exists())
 def test_unsupported_qualified_service_authentication_blocks_before_any_tsa_request(self):
  with tempfile.TemporaryDirectory() as d:
   r,inp=self.setup_case(d);cfg_path=self.qualified_stop(r);cfg=json.loads(cfg_path.read_text());cfg['rfc3161']['stop'][0]['auth']='account';cfg_path.write_text(json.dumps(cfg))
   p,out,audit=self.run_case(r,inp)
   self.assertNotEqual(p.returncode,0);self.assertIn('authentication mode "account" is not supported',p.stderr);self.assertFalse(out.exists());self.assertFalse(audit.exists())
if __name__=='__main__':unittest.main()
