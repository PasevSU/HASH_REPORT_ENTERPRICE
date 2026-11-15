"""Self-healing tests: the machine provisions what it needs without a human."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from chronoseal import selfheal

PACKAGE_JSON = json.dumps({
    'name': 'pdf-rfc3161',
    'version': '0.0.0-test',
    'type': 'module',
    'exports': {'.': {'import': './index.mjs'}},
}, indent=2)
INDEX_MJS = 'export const ok = true;\n'


def _write_package(directory, manifest=True):
    directory = Path(directory)
    (directory / 'dist').mkdir(parents=True, exist_ok=True)
    (directory / 'package.json').write_text(PACKAGE_JSON, encoding='utf-8')
    (directory / 'index.mjs').write_text(INDEX_MJS, encoding='utf-8')
    (directory / 'dist' / 'index.js').write_text('export default 1;\n', encoding='utf-8')
    if manifest:
        files = {}
        for name in ('package.json', 'index.mjs', 'dist/index.js'):
            files[name] = selfheal._sha256(directory / name)
        (directory / selfheal.NODE_MANIFEST).write_text(json.dumps({
            'upstream_version': '0.0.0-test',
            'scope': 'test fixture',
            'files_sha256': files,
            'note': 'fixture',
        }, indent=2), encoding='utf-8')
    return directory


class SelfHealNodePackageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vendor = _write_package(self.root / 'vendor' / selfheal.NODE_PACKAGE)
        self.installed = self.root / 'node_modules' / selfheal.NODE_PACKAGE
        self.log = []

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_package_is_restored_from_vendor(self):
        self.assertEqual(selfheal.node_package_state(self.root)['state'], 'MISSING')
        report = selfheal.repair_node_package(self.root, log=self.log.append)
        self.assertEqual(report['action'], 'restored from vendor')
        self.assertEqual(report['after'], 'OK')
        self.assertEqual(selfheal.node_package_state(self.root)['state'], 'OK')
        self.assertTrue((self.installed / 'index.mjs').is_file())
        self.assertTrue(any('SELF-HEAL' in line for line in self.log))

    def test_tampered_install_is_replaced_with_the_pinned_copy(self):
        shutil.copytree(self.vendor, self.installed)
        (self.installed / 'dist' / 'index.js').write_text('export default 999;\n', encoding='utf-8')
        state = selfheal.node_package_state(self.root)
        self.assertEqual(state['state'], 'BROKEN')
        self.assertIn('dist/index.js', state['detail'])
        report = selfheal.repair_node_package(self.root, log=self.log.append)
        self.assertEqual(report['action'], 'restored from vendor')
        self.assertEqual((self.installed / 'dist' / 'index.js').read_text(encoding='utf-8'), 'export default 1;\n')

    def test_healthy_install_is_left_untouched(self):
        shutil.copytree(self.vendor, self.installed)
        before = (self.installed / 'index.mjs').stat().st_mtime_ns
        report = selfheal.repair_node_package(self.root, log=self.log.append)
        self.assertEqual(report['action'], 'none')
        self.assertEqual((self.installed / 'index.mjs').stat().st_mtime_ns, before)
        self.assertEqual(self.log, [])

    def test_untrusted_vendor_copy_is_never_installed(self):
        (self.vendor / 'dist' / 'index.js').write_text('tampered\n', encoding='utf-8')
        state = selfheal.node_package_state(self.root)
        self.assertFalse(state['repairable'])
        report = selfheal.repair_node_package(self.root, log=self.log.append)
        self.assertEqual(report['after'], 'MISSING')
        self.assertFalse(self.installed.exists())
        self.assertTrue(any('cannot repair' in line for line in self.log), self.log)
        self.assertTrue(any('dist/index.js' in line for line in self.log), self.log)

    def test_self_check_reports_a_repair_and_stays_offline(self):
        report = selfheal.self_check(self.root, {'repair': {'enabled': True}}, self.log.append, allow_network=False)
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['node_package']['state'], 'OK')
        self.assertEqual(report['actions'][0]['dependency'], 'node:pdf-rfc3161')
        self.assertFalse(report['allow_network'])

    def test_self_check_flags_a_problem_when_repair_is_disabled(self):
        report = selfheal.self_check(self.root, {'repair': {'enabled': False}}, self.log.append, repair=False)
        self.assertFalse(report['ok'])
        self.assertTrue(report['problems'])
        self.assertFalse(self.installed.exists())


class PipelineSelfHealWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        # A real installation always has package.json next to node_modules; Node
        # stops its package-scope walk there. Without it the probe walks up to the
        # user profile, where an unreadable package.json is unrelated to this test.
        (self.root / 'package.json').write_text(
            json.dumps({'name': 'chronoseal-pipeline-fixture', 'private': True}), encoding='utf-8')
        _write_package(self.root / 'vendor' / selfheal.NODE_PACKAGE)

    def tearDown(self):
        self._tmp.cleanup()

    def _pipeline(self, **repair):
        from chronoseal.pipeline import Pipeline
        cfg = {'repair': repair} if repair else {}
        return Pipeline(self.root, cfg, lambda line: None)

    def test_ensure_node_dependency_repairs_then_proves_it_loads(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        state = self._pipeline(enabled=True)._ensure_node_dependency(node)
        self.assertTrue(state['ok'], state)
        self.assertEqual(state['state'], 'AVAILABLE')
        self.assertTrue((self.root / 'node_modules' / selfheal.NODE_PACKAGE / 'index.mjs').is_file())

    def test_ensure_node_dependency_reports_when_repair_is_disabled(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        state = self._pipeline(enabled=False)._ensure_node_dependency(node)
        self.assertFalse(state['ok'])
        self.assertEqual(state['state'], 'MISSING')
        self.assertIn('repair.enabled', state['message'])

    def test_missing_package_message_names_the_reason(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed')
        shutil.rmtree(self.root / 'vendor' / selfheal.NODE_PACKAGE)
        state = self._pipeline(enabled=True)._ensure_node_dependency(node)
        self.assertFalse(state['ok'])
        self.assertIn('not installed', state['message'])


class RepairConfigTests(unittest.TestCase):
    def test_shipped_config_enables_local_repair_only(self):
        cfg = json.loads((Path(__file__).resolve().parents[1] / 'config' / 'config.json').read_text(encoding='utf-8'))
        self.assertTrue(cfg['repair']['enabled'])
        self.assertFalse(cfg['repair']['allow_network'])

    def test_required_modules_follow_the_qualified_stop_policy(self):
        base = selfheal.required_python_modules({'rfc3161': {'require_qualified_stop': False}})
        qualified = selfheal.required_python_modules({'rfc3161': {'require_qualified_stop': True}})
        self.assertEqual(base, selfheal.PYTHON_BASE_MODULES)
        self.assertIn('signxml', qualified)
        self.assertIn('certifi', qualified)


if __name__ == '__main__':
    unittest.main()
