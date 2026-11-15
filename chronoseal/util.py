from pathlib import Path
import hashlib, json, os, tempfile, time

def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def atomic_json(path,obj,attempts=5):
    """Write JSON atomically, tolerating a transient Windows file lock.

    Antivirus/indexer handles and slow SMB clients can make ``os.replace`` fail
    with PermissionError for a moment. An evidence run must not lose a manifest
    because another process looked at the file, so the replace is retried a few
    times before the error is surfaced.
    """
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(obj,indent=2,ensure_ascii=False)
    for attempt in range(max(1,attempts)):
        fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp'); os.close(fd)
        try:
            Path(tmp).write_text(payload,encoding='utf-8')
            os.replace(tmp,path)
            return
        except OSError:
            if attempt+1>=max(1,attempts): raise
            time.sleep(0.2*(attempt+1))
        finally:
            if Path(tmp).exists():
                try: Path(tmp).unlink()
                except OSError: pass
