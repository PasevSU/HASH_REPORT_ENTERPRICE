"""Integration: actual production style factories, not JS-key-only assertions."""
import unittest
from unittest.mock import patch
from reportlab.lib.styles import getSampleStyleSheet
from hash_report_generator.hash_report_core import HashGeneratorCore, _core_style_snapshot

class RealStyleFactoryIntegration(unittest.TestCase):
    def setUp(self):
        self.core = HashGeneratorCore.__new__(HashGeneratorCore)
        self.base = getSampleStyleSheet()

    def test_production_factory_values(self):
        rules = _core_style_snapshot()
        styles = self.core._create_base_styles(self.base)
        explain = self.core._create_explanatory_styles(self.base)
        self.assertEqual(styles['title_style'].spaceAfter, rules['CORE_PARAGRAPH_LAYOUT']['title_style']['space_after'])
        from hash_report_generator.pdf_object_rules import unicode_font
        self.assertEqual(styles['header_style'].fontName, unicode_font(rules['CORE_PARAGRAPH_LAYOUT']['header_style']['font_name']))
        self.assertEqual(styles['hash_style'].wordWrap, rules['CORE_PARAGRAPH_BEHAVIOR']['hash_style']['word_wrap'])
        self.assertEqual(explain['heading_style'].spaceBefore, rules['CORE_PARAGRAPH_LAYOUT']['explanatory_heading_style']['space_before'])

    def test_js_style_changes_reach_actual_production_factory(self):
        from hash_report_generator import style_loader
        original = style_loader.load_styles()
        altered = dict(original)
        altered['CORE_PARAGRAPH_LAYOUT'] = {**original['CORE_PARAGRAPH_LAYOUT'], 'title_style': {'space_after': 23, 'alignment': 2}}
        with patch.object(style_loader, 'load_styles', return_value=altered):
            changed = self.core._create_base_styles(self.base)['title_style']
        self.assertEqual((changed.spaceAfter, changed.alignment), (23, 2))
        normal = self.core._create_base_styles(self.base)['title_style']
        self.assertNotEqual(normal.spaceAfter, changed.spaceAfter)

    def test_snapshot_loaded_once_per_factory(self):
        from hash_report_generator import style_loader
        real = style_loader.load_styles()
        with patch.object(style_loader, 'load_styles', return_value=real) as loader:
            self.core._create_base_styles(self.base)
            self.assertEqual(loader.call_count, 1)
        with patch.object(style_loader, 'load_styles', return_value=real) as loader:
            self.core._create_explanatory_styles(self.base)
            self.assertEqual(loader.call_count, 1)

    def test_fail_closed_missing_layout(self):
        from hash_report_generator import style_loader
        rules = style_loader.load_styles()
        bad = {k:v for k,v in rules.items() if k!='CORE_PARAGRAPH_LAYOUT'}
        with patch.object(style_loader, 'load_styles', return_value=bad):
            with self.assertRaises(KeyError):
                self.core._create_base_styles(self.base)
