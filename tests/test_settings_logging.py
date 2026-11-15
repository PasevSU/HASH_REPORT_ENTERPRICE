import tempfile, unittest, json, sys
from pathlib import Path
from chronoseal.settings import save,load
from chronoseal.logging_bundle import SessionLogger
class SL(unittest.TestCase):
 def test_settings_unicode_roundtrip_atomic(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'настройки.json'; x={'път':'C:/Тест/ä.pdf'}; save(p,x); self.assertEqual(load(p),x); self.assertFalse(p.with_suffix('.json.tmp').exists())
 def test_logging_uses_configured_executable_paths(self):
  with tempfile.TemporaryDirectory() as d:
   s=SessionLogger(Path(d)); data=s.snapshot(Path(d),{'tools':{'node':sys.executable,'openssl':sys.executable}}); self.assertEqual(data['configured_tools']['node'],sys.executable); self.assertEqual(data['configured_tools']['openssl'],sys.executable); self.assertTrue((s.dir/'environment.json').is_file())
 def test_command_record_complete(self):
  with tempfile.TemporaryDirectory() as d:
   s=SessionLogger(Path(d)); s.command(['x','y'],Path(d),7,'out','err'); r=json.loads((s.commands/'001.json').read_text()); self.assertEqual((r['returncode'],r['stdout'],r['stderr']),(7,'out','err'))
if __name__=='__main__':unittest.main()
