#!/usr/bin/env python3
"""Read-only PDF geometry audit: bounds and overlapping blocks. Does not alter signatures."""
import argparse, json, fitz
from pathlib import Path

def audit(path, *, left=20, right=20, top=25, bottom=20):
    pdf=fitz.open(path); pages=[]
    for number,page in enumerate(pdf,1):
        w,h=page.rect.width,page.rect.height; mm=72/25.4
        content=[]; outside=[]
        for block in page.get_text('blocks'):
            x0,y0,x1,y1,text,*_=block
            if not text.strip(): continue
            record={'bbox':[round(x,2) for x in (x0,y0,x1,y1)],'sample':text[:100].replace('\n',' ')}
            content.append(record)
            if x0 < 0 or y0 < 0 or x1 > w or y1 > h: outside.append(record)
        pages.append({'page':number,'size_pt':[w,h],'text_blocks':len(content),'outside_media_box':outside,'minimum_margin_mm':{'left':left,'right':right,'top':top,'bottom':bottom},'note':'Headers and footers may intentionally occupy reserved margin zones; inspect renders for visual defects.'})
    return {'input':str(path),'pages':pages,'status':'FAIL' if any(p['outside_media_box'] for p in pages) else 'GEOMETRY_ONLY_PASS','limitations':'Cannot certify balanced columns, page breaks, table contrast, or signature validity.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('pdf'); ap.add_argument('--output'); a=ap.parse_args(); result=audit(a.pdf); value=json.dumps(result,indent=2,ensure_ascii=False)
    if a.output: Path(a.output).write_text(value+'\n',encoding='utf-8')
    else: print(value)
    raise SystemExit(1 if result['status']=='FAIL' else 0)
