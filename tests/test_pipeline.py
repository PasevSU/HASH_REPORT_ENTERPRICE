import tempfile, unittest, json, threading, time, sys, os, subprocess
from pathlib import Path
from chronoseal.pipeline import Pipeline, Cancelled, PipelineError
class Tests(unittest.TestCase):
 def cfg(self,root):
  a=root/'a.pem'; b=root/'b.pem'; a.write_text('x'); b.write_text('y')
  return {'tools':{},'generator':{},'rfc3161':{'mode':'DUAL-STAMP','require_distinct_providers':True,'start':[{'name':'A','url':'https://a.invalid','trust_root_files':[str(a)]}],'stop':[{'name':'B','url':'https://b.invalid','trust_root_files':[str(b)]}]}}
 def bridge(self,r):
  (r/'bridge').mkdir(); (r/'bridge'/'stamp.mjs').write_text('')
 def test_pdf_requires_generator_for_hash_report(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF-1.4'); _,issues,_=Pipeline(r,self.cfg(r)).preflight(pdf,'combined'); self.assertTrue(any('Generator' in x for x in issues))
 def test_source_requires_generator(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); src=r/'input'; src.mkdir(); _,issues,_=Pipeline(r,self.cfg(r)).preflight(src,'combined'); self.assertTrue(any('Generator' in x for x in issues))
 def test_auto_discovery(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); src=r/'data'; src.mkdir(); gen=r/'hash_report_combined.py'; gen.write_text(''); self.assertEqual(Pipeline(r,self.cfg(r)).discover_generator(src,'combined'),gen)
 def test_configured_package_discovery(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); src=r/'data'; src.mkdir(); pkg=r/'pkg'; pkg.mkdir(); gen=pkg/'hash_report_combined.py'; gen.write_text(''); c=self.cfg(r); c['generator']={'package_dir':str(pkg)}; self.assertEqual(Pipeline(r,c).discover_generator(src,'combined'),gen)
 def test_missing_trust_file_is_blocker(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r); c['rfc3161']['start'][0]['trust_root_files']=[str(r/'missing.pem')]; _,issues,_=Pipeline(r,c).preflight(pdf); self.assertTrue(any('does not exist' in x for x in issues))
 def test_same_provider_topology_blocked(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r); c['rfc3161']['stop'][0]['name']='A'; _,issues,_=Pipeline(r,c).preflight(pdf); self.assertTrue(any('distinct' in x for x in issues))
 def test_enabled_archive_requires_directory_and_database_before_report_processing(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r); c['archive']={'enabled':True,'directory':'','database':''}
   _,issues,_=Pipeline(r,c).preflight(pdf)
   self.assertTrue(any('archive directory is empty' in x for x in issues))
   self.assertTrue(any('database path is empty' in x for x in issues))
 def test_enabled_archive_rejects_file_as_archive_directory(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); archive_file=r/'archive'; archive_file.write_text('not a directory')
   c=self.cfg(r); c['archive']={'enabled':True,'directory':str(archive_file),'database':str(r/'archive.sqlite3')}
   _,issues,_=Pipeline(r,c).preflight(pdf)
   self.assertTrue(any('Report archive path is not a directory' in x for x in issues))
 def test_qualified_stop_requirement_blocks_standard_or_unconfigured_tsa(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r); c['rfc3161']['require_qualified_stop']=True
   _,issues,_=Pipeline(r,c).preflight(pdf)
   self.assertTrue(any('qualified TSA provider is mandatory' in x for x in issues))
   self.assertTrue(any('Court-use release blocked' in x for x in issues))

 def test_qualified_stop_reports_unconfirmed_access_separately_from_published_address(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r)
   c['rfc3161']['require_qualified_stop']=True
   c['rfc3161']['stop'][0].update({
    'name':'B-Trust-QTSA','url':'http://tsa.b-trust.org','qualified':True,'auth':'account',
    'service_access_confirmed':False,'policy_oid':'0.4.0.2023.1.1',
    'trusted_list_service_status':'granted','trusted_list_service_certificate_sha256':'a'*64,
    'trusted_list_service_certificate_file':'trust\\B-Trust\\qualified-tsa-service.pem',
    'trust_root_files':[],
    })
   _,issues,_=Pipeline(r,c).preflight(pdf)
   self.assertTrue(any('contracted service access must be confirmed' in x for x in issues))
   self.assertTrue(any('authentication mode "account" is not supported' in x for x in issues))
   self.assertTrue(any('TSA CA trust chain is not configured' in x for x in issues))
   self.assertFalse(any('the official service address must be configured' in x for x in issues))

 def test_qualified_provider_without_account_auth_still_requires_confirmed_service_access(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); self.bridge(r); pdf=r/'x.pdf'; pdf.write_bytes(b'%PDF'); c=self.cfg(r)
   c['rfc3161']['require_qualified_stop']=True
   c['rfc3161']['stop'][0].update({
    'name':'InfoNotary-QTSA','url':'http://ts.infonotary.com/tsa','qualified':True,'auth':'none',
    'service_access_confirmed':False,'policy_oid':'1.3.6.1.4.1.22144.3.4.1',
    'trusted_list_service_status':'granted','trusted_list_service_certificate_sha256':'a'*64,
    'trusted_list_service_certificate_file':'trust\\InfoNotary\\qualified-timestamp-ca.pem',
    'trust_root_files':['trust\\InfoNotary\\qualified-root.pem'],
    })
   _,issues,_=Pipeline(r,c).preflight(pdf)
   self.assertTrue(any('service access and applicable terms must be confirmed' in x for x in issues))

 def test_cancel_terminates_child_process(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); ev=threading.Event(); pipe=Pipeline(r,{},cancel_event=ev)
   def trigger(): time.sleep(.25); ev.set()
   threading.Thread(target=trigger,daemon=True).start()
   with self.assertRaises(Cancelled): pipe._run([sys.executable,'-c','import time; time.sleep(10)'])

 def test_run_utf8_child_output_handles_checkmark(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); logs=[]; pipe=Pipeline(r,{},log=logs.append)
   env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'; env['PYTHONUTF8']='1'
   pipe._run([sys.executable,'-c',"print('\u2713 Unicode font support enabled')"],env=env,encoding='utf-8')
   self.assertTrue(any('✓ Unicode font support enabled' in x for x in logs))

 def test_generate_forces_utf8_for_windows_console_symbols(self):
  src=(Path(__file__).resolve().parents[1]/'chronoseal'/'pipeline.py').read_text(encoding='utf-8')
  self.assertIn("gen_env['PYTHONIOENCODING']='utf-8'",src)
  self.assertIn("encoding='utf-8'",src)

if __name__=='__main__':unittest.main()

class GeneratorHangRegressionTests(unittest.TestCase):
    def test_generator_python_converts_pythonw_to_console_python_when_sibling_exists(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td); w=d/'pythonw.exe'; c=d/'python.exe'; w.write_bytes(b''); c.write_bytes(b'')
            self.assertEqual(Pipeline._generator_python(str(w)),str(c))

    def test_embedded_generator_report_only_avoids_network_tsa_wait(self):
        root=Path(__file__).resolve().parents[1]
        gen=root/'hash_report_generator'/'hash_report_combined.py'
        with tempfile.TemporaryDirectory() as td:
            d=Path(td); (d/'evidence.txt').write_text('ChronoSeal watchdog regression',encoding='utf-8')
            env=os.environ.copy(); env['PYTHONIOENCODING']='utf-8'; env['PYTHONUTF8']='1'; env['CHRONOSEAL_REPORT_ONLY']='1'
            # The budget only has to separate local generation from a network TSA
            # wait, so it must sit far above the local work: on the SMB share the
            # generator alone needs ~100s, which made the original 30s limit (and
            # then 120s) measure the file system instead of the behaviour.
            budget=float(os.environ.get("CHRONOSEAL_TEST_GENERATOR_BUDGET", "300"))
            started=time.monotonic()
            q=subprocess.run([sys.executable,str(gen),str(d)],cwd=str(gen.parent),env=env,capture_output=True,text=True,encoding='utf-8',timeout=budget)
            elapsed=time.monotonic()-started
            self.assertEqual(q.returncode,0,q.stderr)
            self.assertLess(elapsed,budget)
            reports=[p for p in d.glob('*.pdf') if '_ERLAEUTERUNG' not in p.name.upper()]
            self.assertTrue(reports)
            self.assertTrue(reports[0].read_bytes().startswith(b'%PDF-'))

    def test_run_watchdog_terminates_hanging_child(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'bridge').mkdir(); (root/'bridge'/'stamp.mjs').write_text('')
            p=Pipeline(root,{})
            started=time.monotonic()
            with self.assertRaises(PipelineError):
                p._run([sys.executable,'-c','import time; time.sleep(30)'],timeout=0.5)
            self.assertLess(time.monotonic()-started,5)
