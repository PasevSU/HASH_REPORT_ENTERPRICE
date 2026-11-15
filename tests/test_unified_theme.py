import unittest
from chronoseal.unified_theme import THEME, REPORT_KINDS, report_style, css_text

class TestUnifiedTheme(unittest.TestCase):
    def test_all_report_types_share_theme(self):
        self.assertTrue(all(report_style(kind)['theme'] is THEME for kind in REPORT_KINDS))
    def test_css_print_rules(self):
        css = css_text()
        for token in ('@page', 'size: A4', 'thead', 'page-break-inside: avoid', 'orphans:3', 'widows:3'):
            self.assertIn(token, css)
    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError): report_style('unknown')

if __name__ == '__main__': unittest.main()
