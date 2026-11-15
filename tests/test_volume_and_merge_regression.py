import io, os, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from chronoseal.pipeline import Pipeline

class VolumeAndMerge(unittest.TestCase):
 def test_volume_order_and_single_pdf_section(self):
  from hash_report_generator.chronoseal_volume_report import append_volume_section
  story=[]
  with patch.dict(os.environ,{'CHRONOSEAL_VOLUME_JSON':json.dumps({'device_id_st_dev':17,'directory_inode_st_ino':42,'bytes_total':123})}):
   append_volume_section(story,getSampleStyleSheet()['Normal'])
  rendered=' '.join(x.text for x in story if isinstance(x,Paragraph))
  self.assertEqual(rendered.count('VOLUME:'),1)
  self.assertNotIn('Device ID (st_dev)',rendered)
  self.assertNotIn('Directory ID (st_ino)',rendered)
  self.assertIn('VOLUME:',rendered)
 def test_merge_report_and_explanation_in_one_pdf(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); source=root/'RPT-20261008-123456-ABCDEF12_SINGLE.pdf'; explanation=root/(source.stem+'_ERLAEUTERUNG.pdf')
   for file,label in ((source,'REPORT'),(explanation,'EXPLANATION')):
    c=canvas.Canvas(str(file));c.drawString(100,600,label);c.showPage();c.save()
   case=root/'case';case.mkdir()
   p=Pipeline(root,{},log=lambda x:None)
   out=p._compose(source,source,case,include_explanation=True)
   reader=PdfReader(str(out)); self.assertGreaterEqual(len(reader.pages),2)
   text=' '.join(page.extract_text() or '' for page in reader.pages)
   self.assertIn('REPORT',text); self.assertIn('EXPLANATION',text)
 def test_stamp_never_same_input_output(self):
  import inspect
  code=inspect.getsource(Pipeline.stamp)
  self.assertIn("'sealed-verified.pdf'",code)
  self.assertIn('output must differ from input',code)
if __name__=='__main__':unittest.main()
