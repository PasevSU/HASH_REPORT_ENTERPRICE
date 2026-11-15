from pathlib import Path

def test_explicit_selection_does_not_scan_folder():
    source = (Path(__file__).resolve().parents[1] / "automation" / "Start_Automation.py").read_text(encoding="utf-8")
    block = source.split(" def refresh_files(self):", 1)[1].split(" def add_files(self):", 1)[0]
    assert "iterdir(" not in block
    assert "self.loaded_files" in block
    assert "askopenfilenames" in source
    assert "def remove_files(self):" in source
    assert "def clear_files(self):" in source
