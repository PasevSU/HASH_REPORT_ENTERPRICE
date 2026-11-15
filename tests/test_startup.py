import tempfile, unittest, sys
from pathlib import Path
from unittest.mock import patch
from chronoseal.startup import startup_check
class StartupTests(unittest.TestCase):
 def test_missing_node_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   with patch('chronoseal.startup.executable',return_value=None):
    with patch('chronoseal.startup.shutil.which',return_value=None):
     r,_=startup_check(Path(d),{'tools':{}},False)
     self.assertTrue(any('Node.js' in x for x in r['blockers']))
 def test_bad_node_version_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   def exe(name,configured=None): return sys.executable if name=='node' else None
   with patch('chronoseal.startup.executable',side_effect=exe), patch('chronoseal.startup.node_version',return_value=(20,0,0)):
    r,_=startup_check(Path(d),{'tools':{}},False)
    self.assertTrue(any('22.12.0' in x for x in r['blockers']))
if __name__=='__main__':unittest.main()
