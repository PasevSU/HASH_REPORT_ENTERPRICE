import sys,tempfile,hashlib,json
from pathlib import Path
sys.path.insert(0,'/mnt/data/ChronoSeal_v56_A4_PROVENANCE_DEV')
from chronoseal.pipeline import Pipeline
from reportlab.pdfgen import canvas
from pypdf import PdfReader
with tempfile.TemporaryDirectory() as td:
 d=Path(td); report=d/'RPT-20261008-12345-ABCD_HASHREPORT_TYP_SINGLE.pdf';source=d/'source.pdf'
 c=canvas.Canvas(str(report),pagesize=(595.2756,841.8898));c.drawString(80,720,'Hash report text');c.save()
 c=canvas.Canvas(str(source),pagesize=(842,1191));c.drawString(70,900,'A3 source document');c.save()
 before=hashlib.sha256(source.read_bytes()).hexdigest()
 p=Pipeline(d,{},log=lambda x:None)
 output=p._compose(report,source,d,include_source_pdf=True)
 reader=PdfReader(str(output)); embedded=reader.attachments['source.pdf']
 assert len(reader.pages)==4,len(reader.pages)
 assert abs(float(reader.pages[1].mediabox.width)-842)<0.01
 assert abs(float(reader.pages[1].mediabox.height)-1191-91)<0.01
 assert 'PAGE TEXT HASHES' in reader.pages[1].extract_text() and 'PDF TEXT' in reader.pages[-1].extract_text()
 assert len(embedded)==1 and hashlib.sha256(embedded[0]).hexdigest()==before
 assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 assert json.loads((d/'embedded-original.json').read_text())['verification']=='PASS'
 print('PASS: SINGLE_PDF source geometry and attachment preserved; source text hash appendix added')


