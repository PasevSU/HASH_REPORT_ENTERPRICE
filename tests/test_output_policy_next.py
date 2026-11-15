import unittest
from pathlib import Path
from unittest.mock import patch
from chronoseal.pipeline import Pipeline
class OutputPolicyTests(unittest.TestCase):
 def test_run_accepts_output_dir(self):
  import inspect
  self.assertIn('output_dir',inspect.signature(Pipeline.run).parameters)
 def test_volume_redaction(self):
  from hash_report_generator.chronoseal_volume_report import append_volume_section
  story=[]
  import json
  with patch.dict('os.environ',{'CHRONOSEAL_VOLUME_JSON':json.dumps({'requested_path':r'C:\Users\private\Folder','volume_guid_path':'volume-abc','device_id_st_dev':'secret'})}):append_volume_section(story,None)
  text=' '.join(str(x.text) for x in story if hasattr(x,'text'))
  self.assertNotIn('private',text)
  self.assertNotIn('secret',text)
  self.assertIn('Volume GUID',text)
if __name__=='__main__':unittest.main()
