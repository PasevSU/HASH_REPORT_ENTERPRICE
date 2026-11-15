import unittest
from hash_report_generator.hash_report_core import _core_paragraph_behavior
from hash_report_generator.style_loader import load_styles

class SemanticParagraphBehaviorTests(unittest.TestCase):
    def test_all_five_roles_preserve_word_wrap(self):
        roles = ('table_text_style','hash_style','timestamp_style',
                 'explanatory_small_style','explanatory_table_cell_style')
        for role in roles:
            with self.subTest(role=role):
                self.assertEqual(_core_paragraph_behavior(role, 'word_wrap'), 'WORD')
                self.assertEqual(load_styles()['CORE_PARAGRAPH_BEHAVIOR'][role]['word_wrap'], 'WORD')
    def test_unknown_rule_fails_closed(self):
        with self.assertRaises(KeyError):
            _core_paragraph_behavior('unknown_role', 'word_wrap')
