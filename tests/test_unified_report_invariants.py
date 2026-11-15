import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class UnifiedReportInvariants(unittest.TestCase):
    def test_pipeline_syntax(self):
        ast.parse((ROOT / "chronoseal/pipeline.py").read_text(encoding="utf-8"))

    def test_generated_report_signature_guard(self):
        code = (ROOT / "chronoseal/pipeline.py").read_text(encoding="utf-8")
        self.assertIn("GENERATED_REPORT_ALREADY_SIGNED", code)
        self.assertIn("generated_state = inspect_pdf(report)", code)

    def test_explicit_single_pdf_mode_guard(self):
        code = (ROOT / "chronoseal/pipeline.py").read_text(encoding="utf-8")
        self.assertIn("SINGLE+PDF requires an original PDF", code)

if __name__ == "__main__": unittest.main()
