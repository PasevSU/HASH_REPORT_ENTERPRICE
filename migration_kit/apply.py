#!/usr/bin/env python3
"""Three guarded ways to deploy an already qualified migration tree.
No method changes the source in place without a backup.
"""
import argparse, hashlib, json, shutil, subprocess, tempfile, os
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(root):
    return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
def deploy(source,target,method,patch=None):
    source=Path(source).resolve();target=Path(target).resolve()
    if not source.is_dir(): raise ValueError('Source directory missing')
    if source==target or source in target.parents or target in source.parents: raise ValueError('Overlapping paths refused')
    if method=='atomic':
        if target.exists(): raise FileExistsError('Atomic mode requires a new destination')
        stage=target.with_name(target.name+'.staging')
        if stage.exists(): raise FileExistsError('Staging path occupied')
        shutil.copytree(source,stage); assert manifest(stage)==manifest(source)
        os.replace(stage,target)
    elif method=='overlay':
        if not target.is_dir(): raise ValueError('Overlay requires existing target')
        backup=target.with_name(target.name+'.backup')
        if backup.exists(): raise FileExistsError('Backup exists; refuse overwrite')
        shutil.copytree(target,backup)
        try:
            for p in source.rglob('*'):
                if p.is_file():
                    dst=target/p.relative_to(source);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
            for rel,digest in manifest(source).items():
                if sha(target/rel)!=digest: raise RuntimeError('Verification failed: '+rel)
        except BaseException:
            shutil.rmtree(target);shutil.copytree(backup,target);raise
    elif method=='patch':
        if not target.is_dir() or not patch: raise ValueError('Patch mode needs target and patch')
        git=shutil.which('git')
        if not git:
            raise RuntimeError('Patch mode requires the Git executable. No Git metadata is created; use atomic for a new destination or overlay for an existing folder.')
        patch=Path(patch).resolve()
        def apply_patch(*args):
            result=subprocess.run([git,'apply',*args,str(patch)],cwd=target,capture_output=True,text=True)
            if result.returncode:
                detail=(result.stderr or result.stdout).strip()
                raise RuntimeError('Patch could not be applied to the target'
                                   + (': '+detail if detail else '.')
                                   + ' Check patch compatibility; use atomic or overlay if appropriate.')
        apply_patch('--check')
        backup=target.with_name(target.name+'.backup')
        if backup.exists(): raise FileExistsError('Backup exists')
        shutil.copytree(target,backup)
        try: apply_patch()
        except BaseException:
            shutil.rmtree(target);shutil.copytree(backup,target);raise
    else: raise ValueError('Unknown mode')
    return manifest(target)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('method',choices=['atomic','overlay','patch']);ap.add_argument('source');ap.add_argument('target');ap.add_argument('--patch');args=ap.parse_args()
    print(json.dumps({'files':len(deploy(args.source,args.target,args.method,args.patch)),'mode':args.method}))
