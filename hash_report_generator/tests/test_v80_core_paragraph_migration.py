"""Verify that core paragraph presentation values are sourced from JS and preserved."""
import unittest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from hash_report_generator.hash_report_core import HashGeneratorCore, _core_paragraph_color
from hash_report_generator.style_loader import load_styles

class CoreParagraphMigrationTests(unittest.TestCase):
    EXPECTED = {
        'title_style': '#18354D', 'legal_style': '#2d3748',
        'small_style': '#808080', 'warning_style': '#8b0000',
        'success_style': '#15803d', 'table_text_style': '#000000',
        'hash_style': '#000000', 'header_style': '#f5f5f5',
        'legal_declaration_style': '#000000',
        'timestamp_style': '#000000', 'explanatory_small_style': '#334155',
        'explanatory_heading_style': '#2c3e50',
        'explanatory_subheading_style': '#888888',
        'explanatory_table_header_style': '#f5f5f5',
        'explanatory_table_cell_style': '#000000'
    }
    def test_rules_are_exact_original_colors(self):
        rules=load_styles()['CORE_PARAGRAPH_PRESENTATION']
        self.assertEqual(set(rules), set(self.EXPECTED))
        for key, hex_color in self.EXPECTED.items():
            self.assertEqual(rules[key]['text_color'].lower(), hex_color.lower())
            self.assertEqual(_core_paragraph_color(key), colors.toColor(hex_color))
    def test_actual_paragraph_styles_use_rules(self):
        core=object.__new__(HashGeneratorCore)
        base=getSampleStyleSheet()
        built=core._create_base_styles(base)
        for key in ('title_style','legal_style','small_style','warning_style','success_style','table_text_style','hash_style','header_style','timestamp_style'):
            self.assertEqual(built[key].textColor, _core_paragraph_color(key), key)
        explanatory=core._create_explanatory_styles(base)
        for key, role in [('small_style','explanatory_small_style'),('heading_style','explanatory_heading_style'),('subheading_style','explanatory_subheading_style'),('table_header_style','explanatory_table_header_style'),('table_cell_style','explanatory_table_cell_style')]:
            self.assertEqual(explanatory[key].textColor, _core_paragraph_color(role), key)
    def test_missing_role_fails_closed(self):
        with self.assertRaises(KeyError):
            _core_paragraph_color('unknown_not_a_rule')
