import unittest
from pathlib import Path
from reportlab.platypus import KeepTogether, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from hash_report_generator.pagination_policy import keep_heading_with_first_paragraph, pagination_config

class PaginationV42Tests(unittest.TestCase):
    def test_js_rule_loaded(self):
        self.assertTrue(pagination_config()["heading_first_paragraph_keep_together"])
    def test_heading_grouped(self):
        style = getSampleStyleSheet()["Normal"]
        result = keep_heading_with_first_paragraph(Paragraph("Heading",style), Paragraph("Text",style))
        self.assertIsInstance(result, KeepTogether)
        self.assertEqual(len(result._content), 3)
    def test_orphan_source_removed(self):
        src = (Path(__file__).parents[1]/"hash_report_core.py").read_text(encoding="utf-8")
        self.assertNotIn('story.append(Paragraph("<b>VERFAHRENSHINWEISE FÜR DAS GERICHT</b>", normal_style))',src)

if __name__ == "__main__": unittest.main()
