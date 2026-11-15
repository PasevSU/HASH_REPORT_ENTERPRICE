import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionSafetyTests(unittest.TestCase):
    def test_automation_requires_explicit_unsealed_diagnostics(self):
        for name in ("COMBO.bat", "COMBO_ALL.bat", "SINGLE.bat", "SINGLE_PDF.bat"):
            with self.subTest(wrapper=name):
                text = (ROOT / "automation" / name).read_text(encoding="utf-8")
                gate = text.index('if /I not "%~3"=="--diagnostics-unsealed"')
                invocation = text.index('python "%~dp0')
                self.assertLess(gate, invocation)
                self.assertEqual(text.count("--allow-unsealed-diagnostics"), 1)
                self.assertIn("BLOCKED: this runtime only creates unsealed diagnostic evidence", text)

    def test_installer_checks_python_before_installing_dependencies(self):
        text = (ROOT / "Install_Windows.bat").read_text(encoding="utf-8")
        version_check = text.index("sys.version_info < (3,12)")
        dependency_install = text.index("pip install -r")
        self.assertLess(version_check, dependency_install)
        self.assertIn("Python 3.12 or newer is required", text)


if __name__ == "__main__":
    unittest.main()
