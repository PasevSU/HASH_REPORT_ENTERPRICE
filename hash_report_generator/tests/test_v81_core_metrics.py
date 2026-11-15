import unittest
from hash_report_generator.style_loader import load_styles
from hash_report_generator.hash_report_core import ReportConstants, _core_metric

class CoreMetricMigrationTests(unittest.TestCase):
    def test_exact_metrics(self):
        expected = {'FONT_SIZE_TITLE': 16, 'FONT_SIZE_HEADING': 12, 'FONT_SIZE_SUBHEADING': 10, 'FONT_SIZE_LEGAL': 7.3, 'FONT_SIZE_SMALL': 8, 'FONT_SIZE_TABLE_HEADER': 8, 'FONT_SIZE_TABLE_TEXT': 7, 'FONT_SIZE_TABLE_HASH': 6.5, 'FONT_SIZE_EXPLANATORY_CELL': 7, 'FONT_SIZE_EXPLANATORY_SMALL': 8, 'FONT_SIZE_LEGAL_DECLARATION': 8, 'FONT_SIZE_OTS_HEADER': 7, 'FONT_SIZE_OTS_DETAIL': 7, 'FONT_SIZE_PAGE_NUMBER': 8, 'LEADING_HEADING': 16, 'LEADING_SUBHEADING': 14, 'LEADING_SMALL': 10, 'LEADING_TABLE_TEXT': 9, 'LEADING_TABLE_HASH': 8, 'LEADING_EXPLANATORY_HEADER': 10, 'LEADING_EXPLANATORY_CELL': 9, 'LEADING_EXPLANATORY_SMALL': 10, 'LEADING_LEGAL': 9, 'LEADING_LEGAL_DECLARATION': 10, 'LEADING_OTS_DETAIL': 9}
        self.assertEqual(load_styles()["CORE_REPORT_METRICS"], expected)
        for key, value in expected.items():
            self.assertEqual(getattr(ReportConstants, key), value)
    def test_missing_rule_fails_closed(self):
        with self.assertRaises(KeyError):
            _core_metric("NOT_A_RULE")

