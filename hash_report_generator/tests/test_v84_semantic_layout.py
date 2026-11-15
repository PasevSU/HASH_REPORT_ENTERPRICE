import unittest
from pathlib import Path

class SemanticLayoutTests(unittest.TestCase):
    def test_no_opaque_layout_keys_in_style_factories(self):
        source=(Path(__file__).parents[1]/'hash_report_core.py').read_text(encoding='utf-8')
        section=source.split('    def _create_base_styles(',1)[1].split('    # ========================================================================\n    # СЕКЦИИ ЗА PDF',1)[0]
        for key in ('L1670','L1672','L1677','L1679','L1688','L1704','L1705','L1707','L1708','L1711'):
            self.assertNotIn('hash_report_core__'+key,section)
        self.assertEqual(section.count('_factory_layout('),15)

    def test_js_values_and_fail_closed(self):
        from hash_report_generator.style_loader import load_styles
        rules=load_styles()['CORE_PARAGRAPH_LAYOUT']
        self.assertEqual(sum(len(v) for v in rules.values()),14)
        self.assertEqual(rules['title_style'], {'space_after':12,'alignment':1})
        self.assertEqual(rules['header_style']['font_name'],'Helvetica-Bold')
        with self.assertRaises(KeyError): _=rules['unknown_style']
