"""Enterprise finalization of an EXISTING finalized PDF. Never modifies source PDF.
This is a verification-only handoff, not a TSA stamping orchestrator.
"""
from __future__ import annotations
import argparse, hashlib, json, os, tempfile
from pathlib import Path
from verification_gate import verify as verify_pdf

PROFILES = frozenset({'single','single_pdf','combo','combo_all'})

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def atomic_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.finalization-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def finalize(profile, pdf, roots, output_dir, *, node='node', verifier=verify_pdf):
    if profile not in PROFILES:raise ValueError('Unsupported Enterprise profile')
    pdf=Path(pdf).resolve(strict=True)
    if not pdf.is_file() or pdf.suffix.lower()!='.pdf':raise ValueError('Existing PDF required')
    output_dir=Path(output_dir).resolve();output_dir.mkdir(parents=True,exist_ok=True)
    # Never permit audit paths to replace the source PDF, including symlink aliases.
    for name in ('verification.json', 'finalization.json'):
        candidate=output_dir/name
        if candidate.resolve()==pdf or (candidate.exists() and candidate.samefile(pdf)):
            raise ValueError('Audit output collides with input PDF')
    initial=digest(pdf)
    audit_path=output_dir/'verification.json'
    try:
        audit=verifier(pdf,[Path(x) for x in roots],audit_path,node=node,minimum_timestamps=2)
        errors=list(audit.get('errors',[]))
        # A returned PASS is insufficient: require an actual on-disk gate audit,
        # bound to the same PDF and reporting verified timestamp evidence.
        try:
            recorded=json.loads(audit_path.read_text(encoding='utf-8'))
        except (OSError, ValueError, json.JSONDecodeError):
            recorded={}
            errors.append('missing_or_invalid_verification_audit')
        if recorded.get('status')!='PASS' or recorded.get('pdf_sha256')!=initial:
            errors.append('verification_audit_not_bound_to_pdf')
        count=recorded.get('verified_timestamp_count')
        if type(count) is not int or count<2:
            errors.append('insufficient_verified_timestamps')
        if recorded.get('schema')!='chronoseal.verification-gate/v1':
            errors.append('unrecognized_verification_schema')
        if recorded.get('errors') not in ([],):
            errors.append('verification_audit_contains_errors')
        if recorded.get('minimum_timestamps')!=2:
            errors.append('verification_policy_mismatch')
        library=recorded.get('library_audit')
        if not isinstance(library,dict) or library.get('status')!='PASS' or library.get('input_sha256')!=initial:
            errors.append('library_evidence_missing_or_unbound')
        stamps=library.get('timestamps') if isinstance(library,dict) else None
        if not isinstance(stamps,list) or len(stamps)<2 or any(not isinstance(t,dict) or t.get('verified') is not True or t.get('verification_error') for t in stamps):
            errors.append('individual_timestamp_evidence_invalid')
        if not isinstance(library.get('trust_anchors') if isinstance(library,dict) else None,list) or not library['trust_anchors']:
            errors.append('trust_anchor_evidence_missing')
        if audit.get('pdf_sha256')!=initial or audit.get('verified_timestamp_count')!=count or audit.get('schema')!=recorded.get('schema'):
            errors.append('returned_and_recorded_audit_disagree')
        if audit.get('status')!='PASS':
            errors.append('verification_gate_not_pass')
        status='VERIFIED' if not errors else 'BLOCKED' 
    except Exception as exc:
        status='BLOCKED';errors=['verification_execution_failed',type(exc).__name__]
    if digest(pdf)!=initial:
        status='BLOCKED';errors.append('pdf_changed_during_finalization')
    result={'schema':'chronoseal.enterprise-finalization/v1','profile':profile,'pdf':str(pdf),'pdf_sha256':initial,'verification_audit':str(audit_path),'status':status,'errors':errors,'pdf_modified':False,'report_generation':'NOT_PERFORMED','rfc3161_stamping':'NOT_PERFORMED'}
    atomic_json(output_dir/'finalization.json',result)
    return result

def main():
    ap=argparse.ArgumentParser(description='Verify finalized Enterprise PDF without restamping')
    ap.add_argument('--profile',required=True,choices=sorted(PROFILES));ap.add_argument('--pdf',type=Path,required=True)
    ap.add_argument('--root',action='append',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--node',default='node')
    a=ap.parse_args()
    try:r=finalize(a.profile,a.pdf,a.root,a.output_dir,node=a.node)
    except Exception as exc:
        print('BLOCKED:',type(exc).__name__,str(exc));return 2
    print(r['status'],a.output_dir/'finalization.json');return 0 if r['status']=='VERIFIED' else 1
if __name__=='__main__':raise SystemExit(main())
