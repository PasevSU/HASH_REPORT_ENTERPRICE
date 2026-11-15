from pathlib import Path
import json, os, shutil, subprocess, re

NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,data):
    from .util import atomic_json
    atomic_json(path,data)

EVIDENCE_RETENTION_KEYS = ('keep_tsr', 'keep_certificates', 'keep_validation_json')

def evidence_policy(config):
    """Retention switches are mandatory, not optional.

    An archived report stays verifiable offline only while its RFC3161 timestamp
    response, TSA certificates and validation JSON travel with it. Turning any of
    them off would silently produce an unverifiable evidence package, so the
    policy is enforced instead of being accepted and ignored.
    """
    policy = (config or {}).get('evidence') or {}
    if not isinstance(policy, dict):
        raise ValueError('config.evidence must be a JSON object')
    disabled = [key for key in EVIDENCE_RETENTION_KEYS if policy.get(key) is False]
    if disabled:
        raise ValueError(
            'config.evidence.' + ', config.evidence.'.join(disabled) +
            ' cannot be disabled: an archived report must keep its timestamp response, '
            'TSA certificates and validation JSON to remain verifiable offline.')
    return {key: True for key in EVIDENCE_RETENTION_KEYS}

def executable(name, configured=None):
    if configured:
        p=Path(configured).expanduser()
        if p.is_file(): return str(p)
    hit=shutil.which(name)
    if hit:return hit
    if os.name=='nt':
        candidates={
          'openssl':[r'C:\Program Files\OpenSSL-Win64\bin\openssl.exe',r'C:\Program Files\Git\mingw64\bin\openssl.exe',r'C:\Program Files\Git\usr\bin\openssl.exe'],
          'node':[r'C:\Program Files\nodejs\node.exe']}
        for x in candidates.get(name,[]):
            if Path(x).is_file():return x
    return None

def node_version(node):
    try:
        s=subprocess.run([node,'--version'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10,creationflags=NO_WINDOW).stdout.strip()
        m=re.match(r'v(\d+)\.(\d+)\.(\d+)',s); return tuple(map(int,m.groups())) if m else None
    except Exception:return None
