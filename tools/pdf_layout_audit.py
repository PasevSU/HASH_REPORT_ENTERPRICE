"""Read-only PDF page geometry audit; never rewrites signed evidence."""
import argparse, json
from pathlib import Path
import fitz

def audit(path):
    doc=fitz.open(path); pages=[]; findings=[]
    for i,page in enumerate(doc):
        h,w=page.rect.height,page.rect.width
        blocks=[b for b in page.get_text('blocks') if len(b)>4 and str(b[4]).strip()]
        body=[b for b in blocks if b[1]<h-75 and b[3]>45]
        low=max((b[3] for b in body),default=0)
        unused=round(max(0,(h-75)-low),1)
        text=page.get_text()
        info={'page':i+1,'width_pt':round(w,2),'height_pt':round(h,2),'body_last_y_pt':round(low,1),'unused_body_height_pt':unused,'block_count':len(body)}
        pages.append(info)
        if unused>125:
            findings.append({'page':i+1,'code':'LARGE_UNUSED_BODY_AREA','unused_pt':unused,'severity':'REVIEW'})
        if i>0:
            previous=doc[i-1].get_text()
            if 'CRYPTOGRAPHIC TIMESTAMP STOP:' in previous and ('Processing Duration' in text or 'Verification' in text[:350]):
                findings.append({'page':i+1,'code':'TIMESTAMP_SECTION_CONTINUATION','severity':'REVIEW'})
            if 'ZUSAMMENFASSUNG' in previous and 'Versicherung an Eides statt' in text:
                findings.append({'page':i+1,'code':'SUMMARY_TABLE_ORPHAN_ROW','severity':'FAIL'})
    return {'schema':'chronoseal.layout-audit/v1','source':str(path),'pages':pages,'findings':findings,'status':'FAIL' if any(f['severity']=='FAIL' for f in findings) else 'REVIEW' if findings else 'PASS'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--output');a=p.parse_args()
    result=audit(a.pdf);data=json.dumps(result,indent=2,ensure_ascii=False)
    if a.output:Path(a.output).write_text(data,encoding='utf-8')
    print(data)
