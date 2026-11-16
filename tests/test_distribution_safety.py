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

    def test_embedding_wrappers_use_the_sealed_runner(self):
        # COMBO_PDF / COMBO_ALL_PDF need the real PDF assembly, so they drive
        # chronoseal_cli.py and must never advertise unsealed diagnostics.
        for name in ("COMBO_PDF.bat", "COMBO_ALL_PDF.bat"):
            with self.subTest(wrapper=name):
                text = (ROOT / "automation" / name).read_text(encoding="utf-8")
                self.assertNotIn("--allow-unsealed-diagnostics", text)
                self.assertNotIn("--diagnostics-unsealed", text)
                self.assertIn('chronoseal_cli.py', text)
                self.assertIn('--embed-pdf', text)
                self.assertIn('--embed-position', text)
                self.assertEqual(text.count('if /I not "%POS%"=='), 2)


    def test_js_launcher_reaches_every_report_type_and_both_embedding_routes(self):

        # The clone's menu is the only entry point most users see: a profile or

        # an option the menu cannot name is unreachable in practice.

        data = (ROOT / "js" / "HashReport.bat").read_bytes()

        self.assertNotIn(b"\n", data.replace(b"\r\n", b""), "js/HashReport.bat must stay CRLF")

        text = data.decode("utf-8")

        # A label reference in the dispatch block would match too, so anchor on the label line.

        start = text.index("\n:CYCLEPROFILE")

        cycle = text[start:text.index("goto :MENU", start)]

        for profile in ("auto", "single", "combo", "combo_all", "combo_pdf", "combo_all_pdf",

                        "volume", "file_information_report", "single_pdf"):

            with self.subTest(profile=profile):

                self.assertIn('set "PROFILE=%s"' % profile, cycle)

        self.assertIn("--embed-pdf", text)

        self.assertIn("--embed-position", text)

        self.assertIn("BLOCKED: the included file must be a .pdf", text)

        self.assertIn("12. PDF to include", text)

        self.assertIn("13. Where it goes", text)


    def test_installer_checks_python_before_installing_dependencies(self):
        text = (ROOT / "Install_Windows.bat").read_text(encoding="utf-8")
        version_check = text.index("sys.version_info < (3,12)")
        dependency_install = text.index("pip install -r")
        self.assertLess(version_check, dependency_install)
        self.assertIn("Python 3.12 or newer is required", text)


if __name__ == "__main__":
    unittest.main()
