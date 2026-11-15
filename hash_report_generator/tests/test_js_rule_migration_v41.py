import tempfile
import unittest
from pathlib import Path
from hash_report_generator.style_loader import load_styles
from hash_report_generator.module_loader import load_modules, load_profiles

class JsMigrationTests(unittest.TestCase):
    def test_styles(self):
        rules=load_styles()
        self.assertEqual(rules['PAGE']['width_mm'],210)
        self.assertEqual(rules['PAGE']['left_mm'],20)
    def test_module_profiles(self):
        modules=load_modules(); profiles=load_profiles(modules=modules)
        self.assertTrue(modules); self.assertTrue(profiles)
    def test_dynamic_js_and_no_json_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'one.js').write_text('module.exports = {"custom": {"value": 42}};')
            (root/'ignored.json').write_text('{"wrong":true}')
            self.assertEqual(load_styles(root), {'custom':{'value':42}})
    def test_reject_runtime_access(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'bad.js').write_text('module.exports = require("fs").readFileSync("/etc/passwd");')
            with self.assertRaises(ValueError):load_styles(root)
