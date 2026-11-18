import importlib.util, importlib.machinery, unittest, tempfile, json
from pathlib import Path
from unittest.mock import patch
from chronoseal import i18n
ROOT=Path(__file__).resolve().parents[1]
def load_gui():
 loader=importlib.machinery.SourceFileLoader('chronoseal_gui',str(ROOT/'ChronoSeal_GUI.pyw')); spec=importlib.util.spec_from_loader(loader.name,loader); mod=importlib.util.module_from_spec(spec); loader.exec_module(mod); return mod
class GuiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.m=load_gui()
  # The GUI localises every label from the saved language, so pin English for
  # assertions instead of depending on the developer's last language choice.
  cls._language=i18n.language(); i18n.set_language('en',persist=False)
 @classmethod
 def tearDownClass(cls): i18n.set_language(cls._language,persist=False)
 def make(self):
  a=self.m.ChronoSealDesktop(auto_bootstrap=False); a.withdraw(); a.update_idletasks(); return a
 def test_constructs_real_tk_and_defaults(self):
  a=self.make()
  try:
   self.assertEqual(a.mode.get(),'combined'); self.assertFalse(a.rec.get()); self.assertEqual(len(a.nb.tabs()),6); self.assertEqual(str(a.go['state']),'disabled')
  finally:a.destroy()
 def test_start_is_blocked_before_startup_qualification(self):
  a=self.make()
  try:
   a.target.set('dummy.pdf')
   with patch.object(self.m.messagebox,'showerror') as e:a.start(); e.assert_called_once(); self.assertEqual(str(a.stop['state']),'disabled')
  finally:a.destroy()
 def test_startup_pass_enables_run(self):
  a=self.make()
  try:
   r={'blockers':[],'actions':[]}; a._startup_done(r,ROOT/'x.json'); self.assertTrue(a.startup_ready); self.assertEqual(str(a.go['state']),'normal')
  finally:a.destroy()
 def test_startup_blocker_keeps_run_disabled(self):
  a=self.make()
  try:
   r={'blockers':['x'],'actions':[]};
   with patch.object(self.m.messagebox,'showerror'):a._startup_done(r,ROOT/'x.json')
   self.assertFalse(a.startup_ready); self.assertEqual(str(a.go['state']),'disabled'); self.assertEqual(a.status.get(),'SETUP REQUIRED')
  finally:a.destroy()
 def test_cancel_sets_event_and_status(self):
  a=self.make()
  try:a.cancel_run(); self.assertTrue(a.cancel.is_set()); self.assertIn('Cancellation',a.status.get())
  finally:a.destroy()
if __name__=='__main__':unittest.main()
