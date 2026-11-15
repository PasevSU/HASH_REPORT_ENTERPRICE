import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class DirectLaunchImports(unittest.TestCase):
    def test_both_generators_without_pythonpath(self):
        for name in ("hash_report_single.py", "hash_report_combined.py"):
            with self.subTest(name=name):
                target = ROOT / "hash_report_generator" / name
                env = dict(os.environ)
                env.pop("PYTHONPATH", None)
                code = "import runpy; runpy.run_path(" + repr(str(target)) + ", run_name='__import_smoke__')"
                result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT / "hash_report_generator"), env=env, text=True, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
