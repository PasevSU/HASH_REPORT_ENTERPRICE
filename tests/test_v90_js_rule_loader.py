"""V90 — contract tests for the batched JS rule loader and the style cache.

These tests pin the two promises of the R1/R2 change (see
docu/V90_JS_CAPABILITY_ANALYSIS_BG.md):

* the merged style payload is byte-for-byte what the previous per-file loader
  produced (golden SHA-256), and
* the hardening that used to happen in Python now happens in the Node runner
  with exactly the same rejections.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hash_report_generator import js_rules, style_loader

GOLDEN_SHA256 = "8fc6eceba632695a8b7892306bc65e9a604686c92c0a2047ef8a4dcdda28ae66"


def _payload(styles):
    return json.dumps(styles, sort_keys=True, ensure_ascii=True)


def _write_rule(folder, name, body):
    path = Path(folder) / name
    path.write_text(body, encoding='utf-8')
    return path


class StylePayloadIdentityTests(unittest.TestCase):
    """R1 must not change a single byte of the merged rules."""

    def setUp(self):
        style_loader.invalidate()

    def test_merged_style_payload_is_unchanged(self):
        digest = hashlib.sha256(_payload(style_loader.load_styles()).encode()).hexdigest()
        self.assertEqual(digest, GOLDEN_SHA256)

    def test_every_mandatory_section_is_present(self):
        styles = style_loader.load_styles()
        self.assertEqual(style_loader.REQUIRED - styles.keys(), set())

    def test_repeated_loads_spawn_one_node_process(self):
        with patch.object(js_rules.subprocess, 'run', wraps=js_rules.subprocess.run) as run:
            for _ in range(4):
                style_loader.load_styles()
        self.assertEqual(run.call_count, 1, 'the four call sites must share one load')

    def test_a_consumer_cannot_poison_the_cache(self):
        first = style_loader.load_styles()
        first['PAGE']['injected_by_test'] = True
        self.assertNotIn('injected_by_test', style_loader.load_styles()['PAGE'])

    def test_loads_stay_deterministic(self):
        self.assertEqual(_payload(style_loader.load_styles()),
                         _payload(style_loader.load_styles()))


class StyleCacheContractTests(unittest.TestCase):
    """The cache is process-scoped and explicitly invalidatable."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / 'style'
        self.folder.mkdir()
        _write_rule(self.folder, '10_alpha.js', 'module.exports = {ALPHA: 1};')

    def tearDown(self):
        style_loader.invalidate(self.folder)
        self._tmp.cleanup()

    def test_a_custom_directory_is_loaded_once(self):
        with patch.object(js_rules.subprocess, 'run', wraps=js_rules.subprocess.run) as run:
            style_loader.load_styles(self.folder)
            style_loader.load_styles(self.folder)
        self.assertEqual(run.call_count, 1)

    def test_an_edited_rule_needs_an_explicit_invalidate(self):
        self.assertEqual(style_loader.load_styles(self.folder)['ALPHA'], 1)
        _write_rule(self.folder, '10_alpha.js', 'module.exports = {ALPHA: 2};')
        self.assertEqual(style_loader.load_styles(self.folder)['ALPHA'], 1,
                         'a cached load must not re-read the network share')
        style_loader.invalidate(self.folder)
        self.assertEqual(style_loader.load_styles(self.folder)['ALPHA'], 2)

    def test_documents_merge_in_file_name_order(self):
        _write_rule(self.folder, '20_beta.js', 'module.exports = {BETA: 2};')
        styles = style_loader.load_styles(self.folder)
        self.assertEqual(sorted(styles), ['ALPHA', 'BETA'])

    def test_a_duplicate_section_fails_closed(self):
        _write_rule(self.folder, '20_alpha.js', 'module.exports = {ALPHA: 9};')
        with self.assertRaises(ValueError):
            style_loader.load_styles(self.folder)


class RuleLoaderRejectionTests(unittest.TestCase):
    """Every hardening rule of the old loader still rejects, now from Node."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / 'style'
        self.folder.mkdir()
        _write_rule(self.folder, '00_page.js', 'module.exports = {PAGE: 1};')

    def tearDown(self):
        self._tmp.cleanup()

    def _read(self, name):
        return js_rules.read_js_rules(self.folder, [self.folder / name])

    def test_a_rule_outside_the_directory_is_rejected(self):
        outside = _write_rule(self.root, 'elsewhere.js', 'module.exports = {X: 1};')
        with self.assertRaises(ValueError):
            js_rules.read_js_rules(self.folder, [outside])

    def test_a_relative_escape_is_rejected_without_touching_the_disk(self):
        _write_rule(self.root, 'elsewhere.js', 'module.exports = {X: 1};')
        with self.assertRaises(ValueError):
            js_rules.read_js_rules(self.folder, ['../elsewhere.js'])

    def test_a_non_js_suffix_is_rejected(self):
        _write_rule(self.folder, 'rules.txt', 'module.exports = {X: 1};')
        with self.assertRaises(ValueError):
            self._read('rules.txt')

    def test_a_missing_rule_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self._read('99_missing.js')
        self.assertIn('missing', str(caught.exception).lower())

    def test_a_directory_named_like_a_rule_is_rejected(self):
        (self.folder / 'nested.js').mkdir()
        with self.assertRaises(ValueError):
            self._read('nested.js')

    def test_an_oversized_rule_is_rejected(self):
        _write_rule(self.folder, 'huge.js', '/* ' + 'x' * 200001 + ' */ module.exports = {};')
        with self.assertRaises(ValueError) as caught:
            self._read('huge.js')
        self.assertIn('large', str(caught.exception).lower())

    def test_a_rule_that_exports_a_non_object_is_rejected(self):
        _write_rule(self.folder, 'scalar.js', 'module.exports = 5;')
        with self.assertRaises(ValueError):
            self._read('scalar.js')

    def test_a_runaway_rule_hits_the_vm_timeout(self):
        _write_rule(self.folder, 'loop.js', 'module.exports = {}; while (true) {}')
        with self.assertRaises(ValueError):
            self._read('loop.js')

    def test_a_symlinked_rule_is_rejected(self):
        outside = _write_rule(self.root, 'elsewhere.js', 'module.exports = {X: 1};')
        link = self.folder / 'linked.js'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest('symlinks are not permitted: ' + str(exc))
        with self.assertRaises(ValueError):
            self._read('linked.js')

    def test_a_symlinked_rule_inside_the_directory_is_still_rejected(self):
        target = _write_rule(self.folder, 'real.js', 'module.exports = {X: 1};')
        link = self.folder / 'alias.js'
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest('symlinks are not permitted: ' + str(exc))
        with self.assertRaises(ValueError):
            self._read('alias.js')

    def test_a_missing_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            js_rules.read_js_rules(self.root / 'absent', ['00_page.js'])

    def test_several_valid_rules_load_in_one_process(self):
        _write_rule(self.folder, '90_extra.js', 'module.exports = {EXTRA: 2};')
        with patch.object(js_rules.subprocess, 'run', wraps=js_rules.subprocess.run) as run:
            values = js_rules.read_js_rules(self.folder, sorted(self.folder.glob('*.js')))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(len(values), 2)
        self.assertTrue(all(isinstance(v, dict) for v in values))


if __name__ == '__main__':
    unittest.main()
