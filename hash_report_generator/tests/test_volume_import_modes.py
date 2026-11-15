"""Guard against duplicate module identity and script/package import regressions."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "hash_report_generator" / "chronoseal_volume_report.py"

class VolumeImportModesTest(unittest.TestCase):
    def test_package_import(self):
        cmd = [sys.executable, "-c", "import hash_report_generator.chronoseal_volume_report as v; assert callable(v.append_volume_section)"]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_direct_script_execution(self):
        result = subprocess.run([sys.executable, str(MODULE)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_canonical_style_module(self):
        cmd = [sys.executable, "-c", "import hash_report_generator.chronoseal_volume_report as v; import hash_report_generator.pdf_object_rules as p; assert v.volume_block_table_style is p.volume_block_table_style"]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
