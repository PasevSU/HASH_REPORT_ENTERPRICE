"""Real input enumeration and streaming hashing for report modules."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib

MODES = ('single_file', 'current_folder', 'recursive_folder')

def collect_files(source, mode, *, exclude=()):
    if mode not in MODES:
        raise ValueError(f'Unsupported scope: {mode}')
    root = Path(source).resolve(strict=True)
    ignored = {Path(p).resolve() for p in exclude}
    if mode == 'single_file':
        if not root.is_file(): raise ValueError('single_file requires a file')
        return root.parent, [root] if root not in ignored else []
    if not root.is_dir(): raise ValueError('folder scope requires a directory')
    candidates = root.rglob('*') if mode == 'recursive_folder' else root.iterdir()
    files = []
    for p in candidates:
        if p.is_symlink(): continue
        if p.is_file() and p.resolve() not in ignored:
            files.append(p)
    return root, sorted(files, key=lambda p: p.relative_to(root).as_posix().casefold())

def _date(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC'

def inspect_file(path, root, algorithms=('sha256',)):
    p = Path(path)
    allowed = {'sha256','sha512','sha1','md5'}
    if not algorithms or any(a not in allowed for a in algorithms):
        raise ValueError('Invalid hash algorithms')
    before = p.stat()
    hashes = {a:hashlib.new(a) for a in algorithms}
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            for digest in hashes.values(): digest.update(chunk)
    after = p.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise RuntimeError(f'File changed during hashing: {p}')
    return {'path':p.relative_to(root).as_posix(),'type':p.suffix.lower().lstrip('.') or 'file',
            'size_bytes':before.st_size,'created':_date(before.st_ctime),'modified':_date(before.st_mtime),
            **{a:h.hexdigest() for a,h in hashes.items()}}

def build_rows(source,mode,*,algorithms=('sha256',),exclude=()):
    root,files=collect_files(source,mode,exclude=exclude)
    return [dict(index=i,**inspect_file(p,root,algorithms)) for i,p in enumerate(files,1)]
