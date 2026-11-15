from urllib.parse import urlsplit
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, queue, re, subprocess, sys, time, shutil, os, threading, uuid
from .util import sha256, atomic_json, json_safe
from .settings import executable, node_version, evidence_policy
from .storage_identity import inspect_storage, inspect_workspaces, low_space_warning
from . import selfheal

def _load_file_filters():
    """Load the generator's filter grammar without requiring package context."""
    try:
        from hash_report_generator import file_filters as module
        return module
    except ImportError:
        import importlib.util
        path=Path(__file__).resolve().parent.parent/'hash_report_generator'/'file_filters.py'
        spec=importlib.util.spec_from_file_location('chronoseal_file_filters',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

# One matcher is shared by the Selection panel (preview) and the generator
# (actual discovery), so what the operator sees is what gets hashed.
file_filters=_load_file_filters()

def _load_generator_module(name):
    """Load another stdlib-only sibling of the generator without package context."""
    try:
        return __import__('hash_report_generator.'+name, fromlist=['*'])
    except ImportError:
        import importlib.util
        path=Path(__file__).resolve().parent.parent/'hash_report_generator'/(name+'.py')
        spec=importlib.util.spec_from_file_location('chronoseal_'+name,path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

# v5.5.2: an explicit file selection ("Report from files") uses the same
# grammar module as the panel and the generator, so the three can never drift.
file_selection=_load_generator_module('file_selection')

# This stdlib build exposes no ``windowsHide``; a hidden child needs CREATE_NO_WINDOW.
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

class PipelineError(RuntimeError): pass
class Cancelled(PipelineError): pass

class Pipeline:
    def __init__(self, root, config, log=print, session=None, progress=None, cancel_event=None):
        self.root=Path(root).resolve(); self.cfg=config; self.log=log; self.session=session; self.progress=progress or (lambda n,s:None); self.cancel_event=cancel_event or threading.Event()
        self._case_dir=None
    def _check_cancel(self):
        if self.cancel_event.is_set(): raise Cancelled('Operation cancelled by user.')
    @staticmethod
    def _input_mode(target):
        p=Path(target).expanduser()
        return 'combined' if p.is_dir() else 'single'
    def _run(self,args,cwd=None,env=None,encoding=None,timeout=None,idle_timeout=None,stream=False):
        """Run a child process with a progress-aware watchdog.

        timeout      absolute wall-clock cap for the whole run (None = no cap)
        idle_timeout cap for silence only: the child is killed when it produces no
                     output for that long, so slow-but-healthy work on large inputs
                     is never mistaken for a hang
        stream       forward child output to the session log while it runs (throttled)
        """
        self._check_cancel(); cwd=Path(cwd or self.root); self.log('> '+' '.join(map(str,args)))
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
        p=subprocess.Popen(args,cwd=str(cwd),text=True,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,encoding=encoding,errors='replace' if encoding else None,creationflags=creationflags)
        started=time.monotonic(); chunks={'stdout':[],'stderr':[]}; events=queue.Queue()
        # Dedicated readers keep both pipes drained while the child is alive. This
        # avoids the Windows pipe-buffer deadlock on large reports and, unlike
        # communicate(timeout=...), exposes output while the child is still running
        # so the watchdog can tell "slow" apart from "stalled".
        def drain(name,pipe):
            try:
                for line in iter(pipe.readline,''):
                    events.put((name,line))
            except (OSError,ValueError):
                pass
            finally:
                try:pipe.close()
                except OSError:pass
                events.put((name,None))
        for name in ('stdout','stderr'):
            threading.Thread(target=drain,args=(name,getattr(p,name)),daemon=True).start()
        closed=0; last_activity=started; last_emit=0.0; last_heartbeat=started
        tail=[]; last_progress='none recorded'
        def diagnostics():
            # A stall report is only actionable when it says where the child was
            # and what it printed last. Without this a 900s failure is opaque.
            where=f'\nLast reported progress: {last_progress}'
            if tail:return where+'\nLast child output:\n'+'\n'.join('  '+line for line in tail)
            return where+'\nThe child produced no output at all before stalling.'
        def abort(reason):
            self.log(reason); self._terminate_process_tree(p)
            out,err=self._collect(p,chunks,events)
            if self.session:self.session.command(args,cwd,p.returncode,out,err)
        def label():
            for arg in map(str,args[1:]):
                if arg.lower().endswith('.py'):return Path(arg).name
            return Path(str(args[0])).name
        while closed<2:
            try:
                name,line=events.get(timeout=0.15)
            except queue.Empty:
                name=line=None
            now=time.monotonic()
            if line is not None:
                chunks[name].append(line); last_activity=now
                stripped=line.strip()
                if stripped:
                    tail.append(stripped)
                    del tail[:-8]
                    if '[heartbeat]' in stripped:last_progress=stripped
                if stream and now-last_emit>=0.25:
                    last_emit=now; self.log(line.rstrip())
            elif name is not None:
                closed+=1
            if self.cancel_event.is_set():
                abort('Cancellation: terminating child process…')
                raise Cancelled('Operation cancelled by user; active child process was terminated.')
            if timeout is not None and now-started>timeout:
                abort(f'Watchdog: child process exceeded {timeout:.0f}s of total runtime; terminating process tree…')
                raise PipelineError(f'Child process timeout after {timeout:.0f}s of total runtime: {label()}'
                                    +diagnostics())
            if idle_timeout is not None and now-last_activity>idle_timeout:
                abort(f'Watchdog: child process produced no output for {idle_timeout:.0f}s; terminating process tree…')
                raise PipelineError(f'Child process stalled: no output for {idle_timeout:.0f}s: {label()}'
                                    +diagnostics())
            if stream and now-last_heartbeat>=30:
                last_heartbeat=now
                self.log(f'… still running ({now-started:.0f}s, {len(chunks["stdout"])+len(chunks["stderr"])} output lines; '
                         f'{last_progress})')
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Both pipes reached EOF but the process is still alive. That is a
            # stuck child, not a success; terminate it instead of returning a
            # half-dead process with returncode None to the caller.
            abort('Watchdog: child closed its output but did not exit; terminating process tree…')
            raise PipelineError(f'Child process did not exit after closing its output: {label()}')
        out=''.join(chunks['stdout']); err=''.join(chunks['stderr'])
        if self.session:self.session.command(args,cwd,p.returncode,out,err)
        if out:self.log(out.rstrip())
        if err:self.log(err.rstrip())
        if p.returncode:raise PipelineError((err or out or 'command failed').strip())
        self._check_cancel(); return p
    @staticmethod
    def _collect(p,chunks,events,grace=5.0):
        """Drain whatever the child emitted before it was terminated."""
        closed=0; deadline=time.monotonic()+grace
        while closed<2 and time.monotonic()<deadline:
            try:
                name,line=events.get(timeout=0.15)
            except queue.Empty:
                continue
            if line is not None:chunks[name].append(line)
            elif name is not None:closed+=1
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:pass
        return ''.join(chunks['stdout']),''.join(chunks['stderr'])
    def _terminate_process_tree(self,p):
        if p.poll() is not None:return
        if os.name=='nt':
            killed=False
            try:
                q=subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,text=True,timeout=10,
                                 stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
                killed=q.returncode==0
            except Exception:
                killed=False
            if not killed:
                # taskkill can be denied (service account, job object, restricted
                # desktop). A non-zero exit code is not proof the child exited, so
                # always fall back to the direct process handle before waiting.
                try:p.kill()
                except Exception:pass
        else:
            try:p.terminate()
            except Exception:pass
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:p.kill()
            except Exception:pass

    @staticmethod
    def _generator_python(configured):
        py=str(configured or sys.executable)
        if py.lower() in ('python','python3'):py=sys.executable
        pp=Path(py)
        if pp.name.lower()=='pythonw.exe':
            console=pp.with_name('python.exe')
            if console.is_file():return str(console)
        return py

    def _generator_names(self,mode):
        g=self.cfg.get('generator',{}); explicit=g.get('combined_script' if mode=='combined' else 'single_script')
        defaults=['hash_report_combined.py','combined_hash_report.py','hash_report_generator_combined.py'] if mode=='combined' else ['hash_report_single.py','hash_report.py','hash_report_generator.py']
        return [x for x in [explicit,*defaults] if x]
    def discover_generator(self,target,mode):
        t=Path(target).resolve(); g=self.cfg.get('generator',{}); pkg=g.get('package_dir'); roots=[]
        if pkg:
            pp=Path(pkg).expanduser(); roots.append((self.root/pp).resolve() if not pp.is_absolute() else pp)
        roots += [self.root,t if t.is_dir() else t.parent]
        roots += [Path(x).expanduser() for x in g.get('search_roots',[]) if x]
        names={x.lower() for x in self._generator_names(mode)}; seen=set()
        for r in roots:
            try:r=r.resolve()
            except Exception:continue
            if r in seen or not r.exists():continue
            seen.add(r)
            # Preserve the configured/priority order instead of a set's order.
            for name in self._generator_names(mode):
                p=r/name
                if p.is_file():return p
            found=self._find_generator_under(r,names)
            if found:return found
        return None
    _DISCOVERY_SKIP={'.git','.hg','.svn','node_modules','__pycache__','.chronoseal-venv','.cache','.pytest_cache','.venv','venv'}
    def _find_generator_under(self,root,names):
        """Deterministic, bounded filename search (never scans virtualenvs/vendor).

        An unbounded ``rglob`` over the project root can take minutes when a
        virtualenv or ``node_modules`` is present, and an arbitrary match order
        could pick up a stray copy of the generator. Pruning keeps discovery
        predictable; symlinked directories are never followed.
        """
        skip=set(self._DISCOVERY_SKIP)
        if root==self.root:skip.add('vendor')
        try:
            for dirpath,dirnames,filenames in os.walk(root):
                dirnames[:]=sorted(d for d in dirnames if d.lower() not in skip and not d.startswith('.'))
                for filename in sorted(filenames):
                    if filename.lower() in names:return Path(dirpath)/filename
        except OSError:
            return None
        return None
    @staticmethod
    def _linked_entries(directory,limit=50):
        """Direct children that are symlinks or Win32 reparse points."""
        found=[]
        try:
            for entry in directory.iterdir():
                try:
                    attributes=int(getattr(entry.stat(),'st_file_attributes',0) or 0)
                    if entry.is_symlink() or attributes & 0x400:found.append(entry.name)
                except OSError:continue
                if len(found)>=limit:break
        except OSError:
            return found
        return found
    def _repair_enabled(self):
        return bool((self.cfg.get('repair') or {}).get('enabled', True))
    def _repair_network(self):
        return bool((self.cfg.get('repair') or {}).get('allow_network', False))
    def _probe_node_import(self,node,attempts=2):
        """Ask Node whether the pinned package resolves; retry a transient failure."""
        code="import('pdf-rfc3161').then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exit(2)})"
        detail=''
        for attempt in range(max(1,attempts)):
            try:
                q=subprocess.run([node,'--input-type=module','-e',code],cwd=str(self.root),stdin=subprocess.DEVNULL,
                                 capture_output=True,text=True,timeout=30,creationflags=NO_WINDOW)
            except (OSError,subprocess.SubprocessError) as exc:
                detail=f'{type(exc).__name__}: {exc}'
            else:
                if q.returncode==0:return True,''
                detail=((q.stderr or q.stdout or '').strip().splitlines() or ['exit code %s' % q.returncode])[-1]
            if attempt+1<max(1,attempts):time.sleep(0.5)
        return False,detail
    def _ensure_node_dependency(self,node):
        """Verify pdf-rfc3161 on disk, repair it when needed, then prove it loads."""
        state=selfheal.node_package_state(self.root)
        if state['state']!='OK' and self._repair_enabled():
            self.log(f'SELF-HEAL: node_modules/pdf-rfc3161 is {state["state"].lower()} ({state["detail"]}).')
            result=selfheal.repair_node_package(self.root,log=self.log,allow_network=self._repair_network())
            state=selfheal.node_package_state(self.root)
            if result['action']!='none':self.log(f'SELF-HEAL: {result["action"]} -> {state["state"]}.')
        if state['state']=='OK':
            loaded,detail=self._probe_node_import(node)
            if loaded:return {'ok':True,'state':'AVAILABLE','detail':state['detail']}
            return {'ok':False,'state':'BROKEN',
                    'detail':detail,
                    'message':('Node dependency pdf-rfc3161 is installed but cannot be loaded: ' + detail +
                               '. Run npm install, then retry.')}
        hint='The vendored copy under vendor/pdf-rfc3161 is not usable; run npm install.' if not state['repairable'] \
             else 'Automatic repair is disabled in config (repair.enabled).'
        return {'ok':False,'state':'MISSING','detail':state['detail'],
                'message':f'Node dependency pdf-rfc3161 is not installed ({state["detail"]}). {hint}'}
    def preflight(self,target,mode='combined',pdf_embed=False):
        t=Path(target).expanduser().resolve(); issues=[]; warnings=[]
        info={'target':str(t),'input_kind':'pdf_embed' if pdf_embed and t.is_file() and t.suffix.lower()=='.pdf' else 'source'}
        if not t.exists():issues.append(f'Input does not exist: {t}')
        try:
            evidence_policy(self.cfg)
        except ValueError as exc:
            issues.append(str(exc))
        archive = self.cfg.get('archive', {})
        if archive.get('enabled', False):
            archive_directory = str(archive.get('directory') or '').strip()
            archive_database = str(archive.get('database') or '').strip()
            if not archive_directory:
                issues.append('Report archive is enabled but its archive directory is empty.')
            if not archive_database:
                issues.append('Report archive is enabled but its SQLite database path is empty.')
            if archive_directory and archive_database:
                archive_root = Path(archive_directory).expanduser()
                database_path = Path(archive_database).expanduser()
                if not archive_root.is_absolute():
                    archive_root = self.root / archive_root
                if not database_path.is_absolute():
                    database_path = self.root / database_path
                if archive_root.exists() and not archive_root.is_dir():
                    issues.append(f'Report archive path is not a directory: {archive_root}')
                if database_path.exists() and not database_path.is_file():
                    issues.append(f'SQLite archive path is not a file: {database_path}')
        # Preflight the exact Python interpreter running the GUI before generating a report.
        # Never start a partial evidence run if PDF composition dependencies are absent.
        missing = selfheal.missing_python_modules(self.cfg)
        if missing and self._repair_enabled():
            report=selfheal.repair_python_packages(self.root,log=self.log,allow_network=self._repair_network(),cfg=self.cfg)
            if report['action']!='none':
                info['python_repair']=report['action']
                missing = report['after']
        info['pdf_composition_dependencies'] = 'AVAILABLE' if not missing else 'MISSING: ' + ', '.join(missing)
        if missing:
            issues.append('Missing Python PDF dependencies: ' + ', '.join(missing) +
                          '. Run Install_Windows.bat (uses the same Python environment).')
        bridge=self.root/'bridge'/'stamp.mjs'
        if not bridge.exists():issues.append(f'RFC3161 bridge missing: {bridge}')
        node=executable('node',self.cfg.get('tools',{}).get('node')); info['node']=node
        if not node:issues.append('Node.js >=22.12 was not found. Select node.exe in Settings.')
        else:
            nv=node_version(node); info['node_version']='.'.join(map(str,nv)) if nv else 'UNKNOWN'
            if not nv or nv < (22,12,0):issues.append(f'Node.js >=22.12 required; detected {info["node_version"]}')
            else:
                state=self._ensure_node_dependency(node); info['pdf_rfc3161']=state['state']
                if state['detail']:info['pdf_rfc3161_detail']=state['detail']
                if not state['ok']:issues.append(state['message'])
        openssl=executable('openssl',self.cfg.get('tools',{}).get('openssl')); info['openssl']=openssl
        if not openssl:issues.append('OpenSSL is required for independent RFC 3161 verification. Install it or select openssl.exe in Settings.')
        if t.exists():
            gen=self.discover_generator(t,mode); info['generator']=str(gen) if gen else None
            if not gen:issues.append('Hash Report Generator not found. Select its package folder in Settings.')
            if t.is_dir():
                links=self._linked_entries(t)
                info['linked_entries']=len(links)
                if links and not (self.cfg.get('generator',{}) or {}).get('follow_links',False):
                    shown=', '.join(links[:5])+(' …' if len(links)>5 else '')
                    warnings.append(f'{len(links)} linked folder(s)/file(s) will not be followed, so their content '
                                    f'is outside the evidence set: {shown}. Enable generator.follow_links to include them.')
        pol=self.cfg.get('rfc3161',{}); stages=[('START',pol.get('start',[]))]
        if (pol.get('mode') or 'DUAL-STAMP')=='DUAL-STAMP':stages.append(('STOP',pol.get('stop',[])))
        if pol.get('require_qualified_stop'):
            list_cfg=pol.get('trusted_list_validation') or {}
            required_list_fields=('lotl_file','lotl_signer_certificate_file','lotl_signer_sha256','member_tsl_file')
            missing_list_fields=[key for key in required_list_fields if not list_cfg.get(key)]
            if missing_list_fields:
                issues.append('Trusted List validation is unavailable; configure the offline LOTL, OJEU-anchored LOTL signer certificate and SHA-256 pin, and national TSL snapshot.')
            else:
                try:
                    from .trusted_lists import verify_lotl_and_member_tsl, verify_qualified_tsa_service_status
                    def trusted_list_path(field):
                        candidate=Path(list_cfg[field]).expanduser()
                        return candidate if candidate.is_absolute() else (self.root/candidate).resolve()
                    list_result=verify_lotl_and_member_tsl(
                        lotl_path=trusted_list_path('lotl_file'),
                        lotl_signer_certificate_path=trusted_list_path('lotl_signer_certificate_file'),
                        lotl_signer_sha256=list_cfg['lotl_signer_sha256'],
                        member_tsl_path=trusted_list_path('member_tsl_file'),
                        member_tsl_url=list_cfg.get('member_tsl_url') or next(
                            (p.get('trusted_list_source') for p in pol.get('stop',[]) if p.get('qualified') is True),
                            '',
                        ),
                    )
                    info['trusted_list_validation']=list_result
                    for provider in (p for p in pol.get('stop',[]) if p.get('qualified') is True):
                        info['qualified_service_status_preflight']=verify_qualified_tsa_service_status(
                            trusted_list_path('member_tsl_file'),
                            service_name=provider.get('trusted_list_service_name',''),
                            service_certificate_sha256=provider.get('trusted_list_service_certificate_sha256',''),
                            at_time=datetime.now(timezone.utc),
                        )
                except Exception as exc:
                    issues.append(f'Trusted List signature/delegation validation failed: {exc}')
            if (pol.get('mode') or 'DUAL-STAMP')!='DUAL-STAMP':
                issues.append('Qualified STOP requires DUAL-STAMP mode.')
            qualified=[p for p in pol.get('stop',[]) if p.get('qualified') is True]
            if not qualified:
                issues.append('A qualified TSA provider is mandatory for the final STOP timestamp.')
                issues.append('Court-use release blocked: no qualified STOP provider is configured.')
            for p in qualified:
                if not p.get('url') or str(p.get('url')).startswith('REPLACE_'):
                    issues.append(f'{p.get("name","Qualified TSA")}: the official service address must be configured.')
                if p.get('service_access_confirmed') is not True:
                    if p.get('auth')=='account':
                        issues.append(f'{p.get("name","Qualified TSA")}: contracted service access must be confirmed with the provider before live use.')
                    else:
                        issues.append(f'{p.get("name","Qualified TSA")}: service access and applicable terms must be confirmed before live use.')
                auth=p.get('auth','none')
                if auth not in (None, '', 'none'):
                    issues.append(f'{p.get("name","Qualified TSA")}: authentication mode "{auth}" is not supported by the RFC 3161 bridge.')
                if not p.get('policy_oid'):
                    issues.append(f'{p.get("name","Qualified TSA")}: qualified timestamp policy OID is missing.')
                if p.get('trusted_list_service_status')!='granted' or not p.get('trusted_list_service_certificate_sha256'):
                    issues.append(f'{p.get("name","Qualified TSA")}: active Trusted List service identity and certificate fingerprint are required.')
                service_certificate=p.get('trusted_list_service_certificate_file')
                if not service_certificate:
                    issues.append(f'{p.get("name","Qualified TSA")}: Trusted List service identity certificate file is not configured.')
                else:
                    service_path=Path(service_certificate).expanduser()
                    if not service_path.is_absolute():service_path=(self.root/service_path).resolve()
                    if not service_path.is_file():
                        issues.append(f'{p.get("name","Qualified TSA")}: Trusted List service identity certificate does not exist: {service_path}')
                    elif openssl:
                        check=subprocess.run([openssl,'x509','-in',str(service_path),'-noout','-fingerprint','-sha256'],capture_output=True,text=True,timeout=10,
                                             stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
                        fingerprint=re.search(r'Fingerprint=([0-9A-Fa-f:]+)',check.stdout)
                        expected_pin=str(p.get('trusted_list_service_certificate_sha256') or '').replace(':','').strip().lower()
                        observed_pin=fingerprint.group(1).replace(':','').lower() if fingerprint else ''
                        if check.returncode or observed_pin!=expected_pin:
                            issues.append(f'{p.get("name","Qualified TSA")}: service identity certificate does not match the Trusted List fingerprint.')
                pin=str(p.get('trusted_list_service_certificate_sha256') or '').replace(':','').strip().lower()
                roots=p.get('trust_root_files') or []
                if not re.fullmatch(r'[0-9a-f]{64}',pin):
                    issues.append(f'{p.get("name","Qualified TSA")}: invalid Trusted List certificate SHA-256 fingerprint.')
                if not roots:
                    issues.append(f'{p.get("name","Qualified TSA")}: TSA CA trust chain is not configured; the service identity certificate is not a trust anchor.')
        for stage,providers in stages:
            if not providers:issues.append(f'{stage}: no TSA provider configured')
            for p in providers:
                name=p.get('name','unnamed'); url=str(p.get('url') or '')
                if not url or url.startswith('REPLACE_'):issues.append(f'{stage}/{name}: TSA endpoint is not configured')
                if url and not url.startswith('REPLACE_') and not url.lower().startswith('https://'):warnings.append(f'{stage}/{name}: TSA endpoint is not HTTPS; request privacy is not protected (token integrity is still verified)')
                roots=p.get('trust_root_files') or []
                if not roots:issues.append(f'{stage}/{name}: approved TSA trust certificate/chain is not configured')
                for f in roots:
                    fp=Path(f).expanduser()
                    if not fp.is_absolute():fp=(self.root/fp).resolve()
                    if not fp.is_file():issues.append(f'{stage}/{name}: trust certificate does not exist: {fp}')
                    elif openssl:
                        q=subprocess.run([openssl,'x509','-in',str(fp),'-noout','-subject','-issuer'],capture_output=True,text=True,timeout=10,
                                         stdin=subprocess.DEVNULL,creationflags=NO_WINDOW)
                        if q.returncode:issues.append(f'{stage}/{name}: trust certificate cannot be parsed by OpenSSL: {fp}')
        if pol.get('require_distinct_providers') and stages[-1][0]=='STOP':
            def ident(p):
                u=urlsplit(str(p.get('url') or '').strip().lower())
                return str(p.get('name') or '').strip().lower(),(u.netloc+u.path.rstrip('/')) or None
            starts=[ident(p) for p in pol.get('start',[])]; stops=[ident(p) for p in pol.get('stop',[])]
            if starts and stops and not any(all(s[0]!=x[0] and (not s[1] or s[1]!=x[1]) for s in starts) for x in stops):issues.append('STOP has no provider distinct from START (name or endpoint)')
        return info,issues,warnings
    def generate(self,target,mode='combined',recursive=False,include_explanation=False,filters=None,files=None):
        mode=self._input_mode(target); recursive=bool(recursive and Path(target).is_dir())
        # v5.5.2: an explicit selection replaces folder discovery entirely. Type
        # filters describe a folder, so they cannot compete with chosen files; both
        # are cleared here instead of silently winning over each other.
        selected=file_selection.parse(files or [])
        if selected:
            recursive=False; filters=[]
            self.log('Explicit file selection: '+file_selection.describe(selected)
                     +'; evidence root: '+str(file_selection.root(selected)))
        sp=self.discover_generator(target,mode)
        if not sp:raise PipelineError('Hash Report Generator not found.')
        self.log(f'Generator discovered: {sp}'); out_glob=self.cfg.get('generator',{}).get('output_glob','*.pdf')
        watch=[sp.parent,Path(target).resolve() if Path(target).is_dir() else Path(target).resolve().parent]
        before={p.resolve():p.stat().st_mtime_ns for w in watch if w.exists() for p in w.glob(out_glob)}
        py=self._generator_python(self.cfg.get('generator',{}).get('python'))
        args=[py,str(sp),str(Path(target).resolve())]
        if recursive:args.append('--recursive')
        # The bundled generator prints Unicode status symbols (e.g. ✓/✅).
        # Windows legacy console code pages (cp1251/cp1252) cannot encode them,
        # so force UTF-8 only for this child process and decode its pipes as UTF-8.
        gen_env=os.environ.copy(); gen_env['PYTHONIOENCODING']='utf-8'; gen_env['PYTHONUTF8']='1'; gen_env['PYTHONUNBUFFERED']='1'; gen_env['CHRONOSEAL_REPORT_ONLY']='1'; gen_env['CHRONOSEAL_VOLUME_JSON']=json.dumps(inspect_storage(target),ensure_ascii=False); gen_env['CHRONOSEAL_INCLUDE_EXPLANATION']='1' if include_explanation else '0'
        policy=self.cfg.get('rfc3161',{})
        providers=[provider for stage in ('start','stop') for provider in policy.get(stage,[])]
        def resolved_certificates(field):
            paths=[]
            for provider in providers:
                configured=provider.get(field,[]) or []
                if isinstance(configured,str):configured=[configured]
                for item in configured:
                    path=Path(item).expanduser()
                    paths.append(str(path if path.is_absolute() else (self.root/path).resolve()))
            return paths
        gen_env['CHRONOSEAL_TSA_TRUST_ROOTS']=json.dumps(resolved_certificates('trust_root_files'))
        gen_env['CHRONOSEAL_TSA_INTERMEDIATES']=json.dumps(
            resolved_certificates('intermediate_certificate_files')
            + resolved_certificates('embed_certificate_files')
            + resolved_certificates('trusted_list_service_certificate_file')
        )
        gcfg=self.cfg.get('generator',{})
        # Discovery policy reached the generator through its environment so the
        # generator stays a stand-alone script with no ChronoSeal imports.
        gen_env['CHRONOSEAL_ALLOW_UNREADABLE_FILES']='1' if gcfg.get('allow_unreadable_files',False) else '0'
        gen_env['CHRONOSEAL_FOLLOW_LINKS']='1' if gcfg.get('follow_links',False) else '0'
        # v5.5.0: file-type selection and the heartbeat cadence travel in the same
        # environment channel. Both reproduce v5.4.0 behaviour when unset.
        filters=file_filters.parse(filters or [])
        gen_env['CHRONOSEAL_INCLUDE_PATTERNS']=json.dumps(filters)
        gen_env['CHRONOSEAL_EXPLICIT_FILES']=file_selection.to_env(selected)
        gen_env['CHRONOSEAL_FILTER_CASE_SENSITIVE']='1' if gcfg.get('filter_case_sensitive',False) else '0'
        heartbeat=float(gcfg.get('heartbeat_seconds',30) or 0)
        gen_env['CHRONOSEAL_HEARTBEAT_SECONDS']=str(heartbeat)
        if self._case_dir:gen_env['CHRONOSEAL_EVIDENCE_DIR']=str(self._case_dir)
        timeout=float(gcfg.get('timeout_seconds',0) or 0) or None
        idle_timeout=float(gcfg.get('idle_timeout_seconds',900) or 0) or None
        self.log('Budget: '+('no absolute cap' if timeout is None else f'absolute cap {timeout:.0f}s')
                 +'; '+('no idle timeout' if idle_timeout is None else f'idle timeout {idle_timeout:.0f}s')
                 +' (a large input is limited by progress, not by total runtime)')
        self.log('Heartbeat: '+('disabled' if heartbeat<=0 else f'every {heartbeat:.0f}s')
                 +'; file type filters: '+file_filters.describe(filters)
                 +('; explicit file selection: '+str(len(selected))+' file(s)' if selected else ''))
        if heartbeat>0 and idle_timeout is not None and idle_timeout<3*heartbeat:
            self.log(f'WARNING: idle timeout {idle_timeout:.0f}s is less than three heartbeat intervals '
                     f'({heartbeat:.0f}s); a slow but healthy run could be mistaken for a stall.')
        try:
            self._run(args,cwd=sp.parent,env=gen_env,encoding='utf-8',timeout=timeout,idle_timeout=idle_timeout,stream=True)
        except BaseException:
            # A killed child can leave a truncated report behind. Delete the partial
            # output so a later run can never mistake it for a finished report.
            for w in watch:
                if not w.exists():continue
                for p in w.glob(out_glob):
                    if not re.search(r'_HASHREPORT_TYP_(SINGLE|COMBO)\.pdf$',p.name,re.I):continue
                    try:
                        rp=p.resolve()
                        if rp not in before or p.stat().st_mtime_ns>before[rp]:
                            p.unlink(); self.log(f'Removed partial report left by the failed run: {p.name}')
                    except OSError:pass
            raise
        candidates=[]
        for w in watch:
            if w.exists():
                for p in w.glob(out_glob):
                    try:
                        rp=p.resolve(); mt=p.stat().st_mtime_ns
                        if rp not in before or mt>before[rp]:candidates.append(p)
                    except OSError:pass
        if not candidates:raise PipelineError('Generator finished but no new/updated PDF was detected; ChronoSeal refuses to guess an old report.')
        # Select only a fresh report of the expected mode; never select an old
        # report, an explanatory document or an arbitrary PDF in the directory.
        expected = 'COMBO' if mode == 'combined' else 'SINGLE'
        matches = [p for p in candidates if re.search(
            rf'_HASHREPORT_TYP_{expected}\.pdf$', p.name, re.I)]
        if len(matches) != 1:
            raise PipelineError(f'Expected exactly one new {expected} report; found {len(matches)}: '
                                + ', '.join(str(p) for p in matches))
        return matches[0]
    def stamp(self,pdf,case_dir):
        node=executable('node',self.cfg.get('tools',{}).get('node')) or 'node'
        openssl=executable('openssl',self.cfg.get('tools',{}).get('openssl'))
        if not openssl:raise PipelineError('OpenSSL is required for independent RFC 3161 verification.')
        bridge=self.root/'bridge'/'stamp.mjs'
        out=Path(case_dir)/'sealed-verified.pdf'; audit=Path(case_dir)/'rfc3161-audit.json'
        if out.resolve()==Path(pdf).resolve():raise PipelineError('RFC3161 output must differ from input')
        from .pdf_preflight import inspect_pdf
        state=inspect_pdf(pdf)
        if state['signed']:
            raise PipelineError(f"INPUT_ALREADY_SIGNED: {len(state['signatures'])} existing PDF signatures. Do not stamp again; select an unsigned source or verify the signed PDF independently.")
        stamp_env=os.environ.copy()
        stamp_env['CHRONOSEAL_OPENSSL']=openssl
        stamp_env['CHRONOSEAL_PYTHON']=sys.executable
        # A wedged bridge (dead TSA socket, stuck OpenSSL child) must not hang a
        # headless run forever: bound it, and stream so progress stays visible.
        rfc=self.cfg.get('rfc3161',{})
        timeout=float(rfc.get('timeout_seconds',3600) or 0) or None
        idle_timeout=float(rfc.get('idle_timeout_seconds',900) or 0) or None
        self.log('RFC3161 budget: '+('no absolute cap' if timeout is None else f'absolute cap {timeout:.0f}s')
                 +'; '+('no idle timeout' if idle_timeout is None else f'idle timeout {idle_timeout:.0f}s'))
        self._run([node,str(bridge),'--input',str(pdf),'--output',str(out),'--policy',str(self.root/'config'/'config.json'),'--audit',str(audit),'--evidence',str(case_dir)],env=stamp_env,timeout=timeout,idle_timeout=idle_timeout,stream=True)
        if not out.exists() or not audit.exists():raise PipelineError('RFC3161 engine returned success but final PDF/audit is missing')
        a=json.loads(audit.read_text(encoding='utf-8'))
        if a.get('status')!='PASS' or not a.get('final_reverification',{}).get('verified'):raise PipelineError('Final RFC3161 reopen/reverification did not PASS')
        if not a.get('certificate_embedding',{}).get('all_events_pass'):raise PipelineError('Not all configured TSA certificates were proven present in embedded LTV/DSS material')
        pol=self.cfg.get('rfc3161',{})
        if pol.get('require_qualified_stop'):
            stop=next((p for p in pol.get('stop',[]) if p.get('qualified') is True),None)
            evidence=next((e for e in a.get('events',[]) if e.get('stage')=='STOP'),{})
            q=evidence.get('qualified_provider',{})
            if (not stop or not a.get('qualified_stop_required') or
                    not a.get('qualified_stop_profile_verified') or
                    a.get('qualified_timestamp_status')!='VALIDATION_PASS' or
                    q.get('configured') is not True or
                    q.get('observed_policy_oid')!=stop.get('policy_oid') or
                    q.get('trusted_list_service_certificate_sha256')!=stop.get('trusted_list_service_certificate_sha256') or
                    q.get('trusted_list_service_status')!='granted'):
                raise PipelineError('Qualified STOP audit evidence is missing or does not match the configured Trusted List service and timestamp policy.')
        return out,audit
    def _compose(self, report, target, case, include_explanation=False, include_source_pdf=False):
        from pypdf import PdfReader, PdfWriter
        from .page_identity import apply_footer
        report=Path(report); target=Path(target)
        sections=[('report',report)]
        if include_explanation:
            explanations=sorted(report.parent.glob(report.stem+'*ERLAEUTERUNG.pdf'))
            if len(explanations)!=1:
                raise PipelineError('Requested ERLAEUTERUNG missing or ambiguous: '+str(explanations))
            sections.append(('explanation',explanations[0]))
        if include_source_pdf:
            if not target.is_file() or target.suffix.lower()!='.pdf':
                raise PipelineError('Original PDF inclusion requires a single PDF file input')
            if target.resolve()==report.resolve():
                raise PipelineError('Cannot embed input report inside itself')
            # Keep source pages as visible PDF pages AND embed original byte-exact file.
            # Footer is applied only to report pages before source pages are appended.
        writer=PdfWriter(); spans=[]
        for kind,fp in sections:
            first=len(writer.pages)+1
            if kind!='source_pdf':
                reader=PdfReader(str(fp),strict=True)
                if reader.is_encrypted:raise PipelineError('Encrypted report section not supported: '+str(fp))
                for page in reader.pages:writer.add_page(page,excluded_keys=['/Annots'])
            spans.append({'kind':kind,'source':str(fp),'first_page':first,'last_page':len(writer.pages),'sha256':sha256(fp)})
        # Diagnose source provenance before writing/rewriting assembled content.
        # Never normalize a non-A4 source silently or discard evidence pages.
        from hash_report_generator.style_loader import load_styles
        canonical = load_styles()['PAGE']
        pt_per_mm = 72.0 / 25.4
        expected_width = canonical['width_mm'] * pt_per_mm
        expected_height = canonical['height_mm'] * pt_per_mm
        for section in spans:
            for page_number in range(section['first_page'], section['last_page'] + 1):
                candidate = writer.pages[page_number - 1]
                media = candidate.mediabox
                actual_width, actual_height = float(media.width), float(media.height)
                if abs(actual_width - expected_width) > 1 or abs(actual_height - expected_height) > 1:
                    crop = candidate.cropbox
                    raise PipelineError(
                        f'ASSEMBLY_NON_A4 page={page_number}; section={section["kind"]}; '
                        f'source={section["source"]}; source_page={page_number - section["first_page"] + 1}; '
                        f'MediaBox={tuple(round(float(x), 3) for x in (media.left, media.bottom, media.right, media.top))}; '
                        f'CropBox={tuple(round(float(x), 3) for x in (crop.left, crop.bottom, crop.right, crop.top))}; '
                        f'Rotate={candidate.get("/Rotate", 0)}; '
                        f'actual={actual_width:.3f}x{actual_height:.3f}pt; '
                        f'expected={expected_width:.3f}x{expected_height:.3f}pt; '
                        'fix the upstream section; no implicit resizing')
        source_bytes = None
        source_hash = None
        source_reader = None
        source_signature_audit = None
        report_page_count = len(writer.pages)
        source_first_page = None
        source_page_count = 0
        preserve_source_indexes = []
        if include_source_pdf:
            source_bytes=target.read_bytes()
            source_hash=sha256(target)
            from .pdf_preflight import inspect_pdf
            source_signature_audit=inspect_pdf(target)
            source_reader=PdfReader(str(target),strict=True)
            if source_reader.is_encrypted:
                raise PipelineError('SINGLE_PDF_SOURCE_ENCRYPTED: cannot copy source pages')
            source_page_count=len(source_reader.pages)
            if source_page_count==0:
                raise PipelineError('SINGLE_PDF_SOURCE_EMPTY: original has no pages')
            source_first_page=report_page_count+1
            for source_page in source_reader.pages:
                writer.add_page(source_page)
            preserve_source_indexes=list(range(report_page_count, len(writer.pages)))
            spans.append({'kind':'source_pdf','source':str(target),'first_page':source_first_page,
                          'last_page':len(writer.pages),'sha256':source_hash,
                          'geometry_policy':'preserve_original','page_count':source_page_count})
        composed=case/'assembled-before-footer.UNSEALED.pdf'
        with composed.open('wb') as f:writer.write(f)
        match=re.search(r'(RPT-\d{8}-\d+-[A-Fa-f0-9]+)',report.name)
        report_id=match.group(1) if match else report.stem
        version='ChronoSeal Modern Integration DEV v7'
        ready=case/'report-before-rfc3161.UNSEALED.pdf'
        page_manifest=apply_footer(composed,ready,report_id,version,
                                   preserve_pages=preserve_source_indexes,
                                   source_pdf_signature_audit=source_signature_audit)
        page_count=len(PdfReader(str(ready)).pages)
        if include_source_pdf:
            # Source pages are part of the identity pass but remain untouched.
            # Their page-specific text hashes are printed on paired appendix pages.
            final_writer=PdfWriter(clone_from=str(ready))
            final_writer.add_attachment(filename=target.name,data=source_bytes)
            attached=case/'combined-before-rfc3161.UNSEALED.pdf'
            with attached.open('wb') as f:
                final_writer.write(f)
            reopened=PdfReader(str(attached),strict=True)
            if len(reopened.pages)!=page_count:
                raise PipelineError('SINGLE_PDF_VISIBLE_PAGES_OR_IDENTITY_APPENDICES_MISSING')
            embedded=reopened.attachments.get(target.name)
            if isinstance(embedded,(bytes,bytearray)):
                embedded=[bytes(embedded)]
            if not embedded or len(embedded)!=1 or hashlib.sha256(bytes(embedded[0])).hexdigest()!=source_hash:
                raise PipelineError('SINGLE_PDF_EMBED_HASH_MISMATCH')
            for index,original in enumerate(source_reader.pages):
                copied=reopened.pages[report_page_count+index]
                ext=float(page_manifest[report_page_count+index].get('footer_extension_pt',0))
                ow,oh=(float(original.mediabox.width),float(original.mediabox.height))
                if int(original.get('/Rotate',0))%180: ow,oh=oh,ow
                if abs(float(copied.mediabox.width)-ow)>0.01 or abs(float(copied.mediabox.height)-oh-ext)>0.01:
                    raise PipelineError(f'SINGLE_PDF_SOURCE_GEOMETRY_CHANGED page={index+1}')
            if hashlib.sha256(target.read_bytes()).hexdigest()!=source_hash:
                raise PipelineError('SINGLE_PDF_SOURCE_CHANGED_DURING_COMPOSE')
            os.replace(attached,ready)
            signature_audit_path=case/'source-pdf-signature-audit.json'
            atomic_json(signature_audit_path,{
                'source_filename':target.name,
                'source_pdf_sha256':source_hash,
                'attachment_sha256_verified':True,
                'source_signature_audit':source_signature_audit,
                'visible_page_copy_note':(
                    'Visible pages are a derived presentation copy with added footer space. '
                    'Any source PDF signatures authenticate the exact byte-preserved attachment, '
                    'not these derived visible pages or the composed report.'
                ),
            })
            atomic_json(case/'embedded-original.json',{'filename':target.name,'sha256':source_hash,
                        'size':len(source_bytes),'verification':'PASS','visible_pages':source_page_count,
                        'first_visible_page':source_first_page,
                        'text_identity_appendix_pages':1,
                        'signature_audit':str(signature_audit_path),
                        'source_signature_status':source_signature_audit['verification_status']})
        atomic_json(case/'page-identity.json',{'report_id':report_id,'version':version,
                    'sections':spans,'pages':page_count,'page_manifest':page_manifest})
        return ready

    def _make_case_dir(self,evidence_base):
        """Create the private evidence case or fail with an actionable message.

        A read-only input medium, a full volume or a stray file named
        ChronoSeal_Evidence must not surface as a raw OSError traceback.
        """
        case=evidence_base/(time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:12])
        try:
            case.mkdir(parents=True,exist_ok=False)
        except OSError as exc:
            raise PipelineError(
                f'Cannot create the evidence case {case}: {exc}. '
                'The input location must be writable; read-only media, a full volume or a file '
                'named ChronoSeal_Evidence block evidence capture, so choose a writable output directory.') from exc
        return case

    def run(self,target,mode='combined',recursive=False,include_explanation=False,include_source_pdf=False,output_dir=None,filters=None,files=None):
        started=time.time(); target=Path(target).expanduser().resolve(); mode=self._input_mode(target); recursive=bool(recursive and target.is_dir()); self.progress(0,'Preflight')
        filters=file_filters.parse(filters or [])
        # v5.5.2: the operator may name the exact evidence files. The chosen list is
        # the evidence set; the target folder only anchors relative paths, the
        # evidence case and the published report.
        selected=file_selection.parse(files or [])
        if selected:
            if filters:
                raise PipelineError('An explicit file selection and file type filters cannot be '
                                    'combined: the chosen files already are the evidence set. Clear the filters.')
            if mode!='combined':
                raise PipelineError('An explicit file selection always produces a combined report; '
                                    f'select the folder that contains the files instead of {target}.')
            absent=file_selection.missing(selected)
            if absent:
                raise PipelineError('Selected file(s) no longer exist or are not readable: '
                                    +', '.join(str(item) for item in absent[:10]))
            recursive=False
            self.log(file_selection.describe(selected)
                     +'; evidence root: '+str(file_selection.root(selected)))
        if filters and mode!='combined':
            raise PipelineError('File type filters only apply to a folder (combined) report; '
                                'a single-file report has nothing to filter.')
        if include_source_pdf and (not target.is_file() or target.suffix.lower() != '.pdf'):
            raise PipelineError('SINGLE+PDF requires an original PDF file; cannot silently ignore the requested embedding.')
        info,issues,warnings=self.preflight(target,mode,pdf_embed=include_source_pdf); self.log('0/5 Preflight')
        for k,v in info.items():self.log(f'  {k}: {v}')
        try:
            storage_preflight=inspect_storage(target)
            self.log('  STORAGE IDENTITY & CAPACITY: '+json.dumps(storage_preflight,ensure_ascii=False))
        except (OSError,ValueError) as exc:
            raise PipelineError('Storage identity preflight failed: '+str(exc)) from exc
        space_warning=low_space_warning(storage_preflight,self.cfg.get('storage',{}).get('min_free_bytes'))
        if space_warning:warnings.append(space_warning)
        for w in warnings:self.log('WARNING: '+w)
        if issues:raise PipelineError('PRE-FLIGHT BLOCKED:\n - '+'\n - '.join(issues))
        evidence_base=(target if target.is_dir() else target.parent)/'ChronoSeal_Evidence'
        case=self._make_case_dir(evidence_base); self._case_dir=case
        try:
            storage=inspect_workspaces(target,case,target.parent)
        except (OSError,ValueError) as exc:
            raise PipelineError('Storage identity capture failed: '+str(exc)) from exc
        atomic_json(case/'storage-identity.json', storage)
        if self.session:
            (case/'logs').mkdir();
            # logs are copied at completion/failure by GUI
        self.progress(20,'Report'); self._check_cancel()
        self.log('1/5 Generate report'); report=self.generate(target,mode,recursive,include_explanation,filters=filters,files=selected)
        original_hash=sha256(report)
        # Transactional sealing: a generated report is not published under its final RPT name
        # until both START and STOP DocTimeStamp revisions, DSS/Certs and reopen verification PASS.
        # Never overwrite the selected source PDF or publish an internal UNSEALED file.
        base=report.stem
        # Exactly one of three names; never infer PDF embedding from the extension alone.
        if not re.search(r'_HASHREPORT_TYP_(SINGLE|COMBO)$',base,re.I):
            raise PipelineError('Generator returned unexpected report name: '+report.name)
        if info['input_kind']=='pdf_embed':
            if not base.upper().endswith('_SINGLE'):
                raise PipelineError('PDF inclusion requires a SINGLE hash report')
            suffix='_PDF.pdf'
        else:
            suffix='.pdf'
        destination=Path(output_dir).expanduser().resolve() if output_dir else (target if target.is_dir() else target.parent)
        if not destination.is_dir():raise PipelineError('Output directory does not exist: '+str(destination))
        if recursive and mode=='combined':base += '_ALL'
        publish_path=destination/(base+suffix)
        if publish_path.resolve()==target.resolve():raise PipelineError('Output path would overwrite original')
        # The generator writes SINGLE/COMBO at the final pathname. Stage it inside
        # the private case before sealing; the final name must never hold an UNSEALED PDF.
        staged=case/report.name
        if staged.exists():raise PipelineError('Staging path collision: '+str(staged))
        shutil.move(str(report),str(staged))
        if include_explanation:
            candidates=sorted(report.parent.glob(report.stem+'*ERLAEUTERUNG.pdf'))
            if len(candidates)!=1:raise PipelineError('Requested ERLAEUTERUNG missing or ambiguous')
            shutil.move(str(candidates[0]),str(case/candidates[0].name))
        report=staged
        # A generator must supply an unsigned report. Never flatten or copy a
        # previously signed report into a new report and claim it is unsigned.
        from .pdf_preflight import inspect_pdf
        generated_state = inspect_pdf(report)
        if generated_state['signed']:
            raise PipelineError('GENERATED_REPORT_ALREADY_SIGNED: generator output has '
                                f"{len(generated_state['signatures'])} existing signatures; "
                                'refusing composition and repeat timestamping.')
        if publish_path.exists():raise PipelineError('Output already exists; refusing overwrite: '+str(publish_path))
        working=self._compose(report,target,case,include_explanation,info['input_kind']=='pdf_embed')
        self.log('Prepared independent PDF copy: '+str(working))
        self.progress(45,'RFC3161'); self.log('2/5 Independent RFC3161 START + STOP + embedded TSA validation material'); sealed,audit=self.stamp(working,case)
        self.progress(80,'Final verification'); self.log('3/5 Final PDF reopened; exactly two ChronoSeal DocTimeStamp revisions independently reverified')
        # Only the final sealed PDF is published; generated intermediate PDFs are not user deliverables.
        # Retain internal evidence case for independent verification.
        if True:
            try:
                report.unlink()
            except OSError as exc:
                self.log('WARNING: generated intermediate PDF could not be removed: '+str(exc))
        final=publish_path
        final_hash=sha256(sealed); self.log('4/5 Evidence manifest')
        manifest={'schema':'chronoseal.onebutton/v4-dualstamp','source':str(target),'input_kind':info['input_kind'],'mode':mode,'recursive':recursive,'selection_filters':filters or None,
            'selection_files':[str(item) for item in selected] or None,
            'selection_root':str(file_selection.root(selected)) if selected else None,
            'selection_paths':file_selection.relative(selected) if selected else None,'output_directory':str(destination),'include_explanation':include_explanation,'include_source_pdf':include_source_pdf,'page_identity':str(case/'page-identity.json'),'storage_identity':str(case/'storage-identity.json'),'generator':info.get('generator'),'generated_report':str(working),'report_sha256':original_hash,'final_pdf':str(final),'final_sha256':final_hash,'rfc3161_audit':str(audit),'elapsed_seconds':round(time.time()-started,3),'status':'PASS'}
        # Never hide an evidence exclusion: when the operator allowed unreadable
        # files, the generator's audit becomes part of the published manifest.
        discovery_audit=case/'discovery-unreadable.json'
        if discovery_audit.is_file():
            try:
                audit_data=json.loads(discovery_audit.read_text(encoding='utf-8'))
            except (OSError,ValueError) as exc:
                self.log('WARNING: discovery audit present but unreadable: '+str(exc))
            else:
                manifest['discovery_unreadable']=str(discovery_audit)
                manifest['discovery_unreadable_count']=int(audit_data.get('unreadable_count') or 0)
                manifest['discovery_skipped_link_count']=int(audit_data.get('skipped_link_count') or 0)
                manifest['discovery_excluded_by_filter_count']=int(audit_data.get('excluded_by_filter_count') or 0)
                if manifest['discovery_unreadable_count'] or manifest['discovery_skipped_link_count']:
                    self.log('EVIDENCE EXCLUSIONS: %d unreadable file(s), %d link(s) not followed; see %s'
                             % (manifest['discovery_unreadable_count'], manifest['discovery_skipped_link_count'], discovery_audit))
        # The same read-only layout audit is recorded for manual and automation
        # runs because both routes execute Pipeline.run(). A layout REVIEW does
        # not masquerade as a cryptographic failure or alter the signed bytes.
        from .report_quality import audit_layout
        from .unified_report_profile import DEFAULT_PROFILE
        try:
            layout = audit_layout(sealed, **DEFAULT_PROFILE.audit_options())
            layout['file'] = str(final)
            layout['profile'] = DEFAULT_PROFILE.to_dict()
            atomic_json(case/'layout-audit.json', layout)
            manifest['layout_audit'] = str(case/'layout-audit.json')
            manifest['layout_status'] = layout['status']
            if layout['status'] != 'PASS':
                self.log('LAYOUT REVIEW: ' + '; '.join(layout['issues']))
        except Exception as exc:
            manifest['layout_status'] = 'NOT VERIFIED'
            self.log('LAYOUT NOT VERIFIED: ' + str(exc))
        if self.session:
            shutil.copytree(self.session.dir,case/'logs',dirs_exist_ok=True)
            manifest['evidence_logs']=str(case/'logs')
        # The evidence manifest is written as JSON twice below (case copy and
        # archive). A Path object from any subsystem would raise TypeError there
        # and block a finished report, so normalise it at this boundary.
        manifest=json_safe(manifest)
        archive_cfg=self.cfg.get('archive',{})
        if archive_cfg.get('enabled',False):
            archive_root=Path(archive_cfg.get('directory','') or '').expanduser()
            database_path=Path(archive_cfg.get('database','') or '').expanduser()
            if not str(archive_root) or not str(database_path):
                raise PipelineError('Report archive is enabled but its archive directory or SQLite database path is empty.')
            if not archive_root.is_absolute():archive_root=self.root/archive_root
            if not database_path.is_absolute():database_path=self.root/database_path
            from .report_archive import archive_report
            try:
                archive_info=archive_report(
                    archive_root=archive_root,
                    database_path=database_path,
                    report_pdf=sealed,
                    report_name=publish_path.name,
                    evidence_directory=case,
                    run_log=getattr(self.session,'logfile',None),
                    manifest=manifest,
                )
                self.log('[ARCHIVE] Report, manifest, run log, evidence and SQLite record saved: '+archive_info['archive_directory'])
            except Exception as exc:
                raise PipelineError('Report archive/SQLite persistence failed: '+str(exc)) from exc
        atomic_json(case/'manifest.json',manifest)
        # Publish only after the bridge and, when enabled, the durable archive pass.
        # Hard-link creation is atomic and fails rather than overwriting another report.
        temp=publish_path.with_name(publish_path.name+'.'+uuid.uuid4().hex+'.publishing')
        try:
            shutil.copy2(sealed,temp)
            if sha256(temp)!=final_hash:raise PipelineError('Publication checksum mismatch')
            try:
                os.link(temp,publish_path)
            except FileExistsError as exc:
                raise PipelineError('Concurrent publication collision; refusing overwrite: '+str(publish_path)) from exc
            except OSError as exc:
                raise PipelineError('Atomic no-overwrite publication unavailable on this filesystem: '+str(exc)) from exc
        finally:
            if temp.exists():temp.unlink()
        self.progress(100,'PASS'); self.log('5/5 PASS: '+str(final)); return manifest
