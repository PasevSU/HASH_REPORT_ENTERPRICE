"""Synthetic four-profile visual preflight. No TSA or release claims."""
import argparse,sys,tempfile,json
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hash_report_generator.modular_report import render_report

def main(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chronoseal_visual_') as td:
        base=Path(td); nested=base/'nested';nested.mkdir()
        f=base/'Ä_съдебен_документ.pdf'; f.write_bytes(b'%PDF-1.4\nsynthetic sample for hashing, not a real PDF')
        for i in range(38):
            (base/(f'case_{i:03d}_'+('X'*35)+'.eml')).write_bytes(('synthetic '+str(i)).encode())
        for i in range(45): (nested/f'file_{i:03d}.txt').write_text('test '+str(i))
        result={}
        for profile,source,files in [('single',f,[f]),('single_pdf',f,[f]),('combo',base,[]),('combo_all',base,[])]:
            path=output/(profile+'.pdf')
            try:
                render_report(profile,path,source=source,files=files,system={'Operator':'Visual QA','Case':'TEST'},legal_text='Synthetic test document only. No certified timestamp or legal conclusion.')
                reader=PdfReader(str(path)); pages=len(reader.pages)
                if pages<1: raise AssertionError('zero pages')
                extracted='\n'.join(p.extract_text() or '' for p in reader.pages)
                if 'SHA-256' not in extracted: raise AssertionError('missing SHA-256 heading')
                result[profile]={'status':'PASS_RENDER','pages':pages,'bytes':path.stat().st_size,'note':'unsigned synthetic visual sample'}
            except Exception as exc: result[profile]={'status':'FAIL','error':repr(exc)}
        (output/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps(result,indent=2,ensure_ascii=False))
        if any(v['status']=='FAIL' for v in result.values()):raise SystemExit(1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='qualification/output');main(parser.parse_args().output)
