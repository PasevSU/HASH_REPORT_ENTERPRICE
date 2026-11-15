from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'ChronoSeal_GUI.pyw').read_text(encoding='utf-8')
LEGACY=(ROOT/'ChronoSeal_Original_Legacy.py').read_text(encoding='utf-8')
def test_windows_shortcuts_are_installed():
 for x in ('<Control-c>','<Control-v>','<Control-x>','<Control-a>','<Control-Insert>','<Shift-Insert>','<Shift-Delete>','<Button-3>'): assert x in LEGACY
def test_copyable_error_dialog_replaces_pipeline_messagebox():
 assert "def _copyable_error" in LEGACY
 assert "self._copyable_error('ChronoSeal'" in LEGACY
def test_log_and_diagnostics_have_copy_controls():
 assert "Copy all" in S and "Copy selected" in S
 assert "Copy all log" in LEGACY and "self.diag" in LEGACY
