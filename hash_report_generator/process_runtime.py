"""Fail-closed process runtime: UNSEALED evidence preparation only.
No RFC3161 tokens are fabricated; this is not a signed enterprise release.
"""
from __future__ import annotations
import hashlib, json, os, tempfile, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from .module_loader import load_modules, load_profiles
from .hash_table_engine import build_rows

def _sha256(blob): return hashlib.sha256(blob).hexdigest()
def _utc(): return datetime.now(timezone.utc).isoformat()
def _atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.pending-',suffix='.json',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,indent=2,ensure_ascii=False,sort_keys=True);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def _validate_artifact_name(module_id):
    # Module identifiers are supplied by manifests; never allow them to escape run_dir.
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', module_id):
        raise ValueError('Unsafe module identifier: '+repr(module_id))


def _evidence_digest(artifacts):
    """Stable SHA-256 over the ordered module-output commitments (NOT an RFC3161 token)."""
    commitments=[{'module':a['module'],'sha256':a['sha256'],'size_bytes':a['size_bytes']} for a in artifacts]
    payload=json.dumps(commitments,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return _sha256(payload)


def execute(profile_id, source, output_dir, *, modules_dir=None, profiles_dir=None, allow_unsealed=False):
    if not allow_unsealed: raise RuntimeError('BLOCKED: RFC3161 START/STOP is not integrated; explicitly request unsealed diagnostic execution')
    modules=load_modules(modules_dir); profiles=load_profiles(profiles_dir,modules)
    if profile_id not in profiles: raise ValueError('Unknown report profile: '+profile_id)
    profile=profiles[profile_id]; root=Path(source).resolve(strict=True)
    for module_id in profile['modules']: _validate_artifact_name(module_id)
    out=Path(output_dir).resolve(); out.mkdir(parents=True,exist_ok=True)
    if root.is_dir() and (out==root or root in out.parents): raise ValueError('Output directory must be outside the scanned directory')
    run_id='RUN-'+uuid.uuid4().hex; run_dir=out/run_id;run_dir.mkdir()
    manifest={'schema_version':1,'run_id':run_id,'profile':profile_id,'source':str(root),'started_utc':_utc(),'status':'UNSEALED_RUNNING','rfc3161_start':'NOT_VERIFIED','rfc3161_stop':'NOT_VERIFIED','steps':[],'artifacts':[],'release_status':'BLOCKED'}
    _atomic_json(run_dir/'manifest.json',manifest)
    started=time.monotonic_ns()
    try:
        for module_id in profile['modules']:
            m=modules[module_id];t=time.monotonic_ns();step={'module':module_id,'type':m['type'],'started_utc':_utc(),'status':'RUNNING'}
            manifest['steps'].append(step);_atomic_json(run_dir/'manifest.json',manifest)
            if m['type']=='hash_table':
                rows=build_rows(root,profile.get('input_scope','single_file'),algorithms=tuple(m.get('algorithms',['sha256'])))
                result={'scope':profile.get('input_scope','single_file'),'count':len(rows),'total_size_bytes':sum(x['size_bytes'] for x in rows),'records':rows}
            elif m['type']=='file_information':
                if not root.is_file():raise ValueError('file_information requires a file')
                rows=build_rows(root,'single_file',algorithms=('sha256',))
                result={'file':rows[0]}
            elif m['type']=='key_values':
                result={'status':'NOT_SUPPLIED','fields':{}}
            elif m['type']=='text':
                result={'status':'NOT_SUPPLIED','text':None}
            else:raise ValueError('No trusted execution engine for '+module_id)
            payload=json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            artifact=run_dir/(module_id+'.json');_atomic_json(artifact,result)
            digest=_sha256(artifact.read_bytes())
            manifest['artifacts'].append({'module':module_id,'path':artifact.name,'sha256':digest,'size_bytes':artifact.stat().st_size})
            step.update(status='PASS',finished_utc=_utc(),elapsed_ns=time.monotonic_ns()-t,output_sha256=digest)
            _atomic_json(run_dir/'manifest.json',manifest)
        manifest['evidence_commitment_sha256']=_evidence_digest(manifest['artifacts'])
        manifest['status']='UNSEALED_COMPLETE'
    except Exception as e:
        manifest['status']='FAILED';manifest['error']={'type':type(e).__name__,'message':str(e)}
        if manifest['steps'] and manifest['steps'][-1]['status']=='RUNNING':manifest['steps'][-1]['status']='FAILED'
        raise
    finally:
        manifest['finished_utc']=_utc();manifest['elapsed_ns']=time.monotonic_ns()-started
        _atomic_json(run_dir/'manifest.json',manifest)
    return run_dir

def verify(run_dir):
    root=Path(run_dir);manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    problems=[]
    for a in manifest.get('artifacts',[]):
        try:
            _validate_artifact_name(a['module'])
            if a['path'] != a['module']+'.json': raise ValueError('Unexpected artifact path')
            path=root/a['path']
            if path.is_symlink() or not path.is_file() or _sha256(path.read_bytes())!=a['sha256'] or path.stat().st_size!=a['size_bytes']:
                raise ValueError('Artifact missing or modified')
        except (KeyError, ValueError, OSError, TypeError):
            problems.append(str(a.get('path','INVALID')))
    expected=manifest.get('evidence_commitment_sha256')
    commitment_ok=(isinstance(expected,str) and expected==_evidence_digest(manifest.get('artifacts',[])))
    complete=manifest.get('status')=='UNSEALED_COMPLETE' and all(s.get('status')=='PASS' for s in manifest.get('steps',[]))
    return {'artifacts_integrity':'PASS' if not problems else 'FAILED',
            'invalid_artifacts':problems,
            'evidence_commitment':'PASS' if commitment_ok else 'FAILED',
            'process_complete':bool(complete),
            'rfc3161':'NOT_VERIFIED','enterprise_release':'BLOCKED'}
