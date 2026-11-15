"""Unreadable evidence files must never vanish from a hash report silently."""
import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hash_report_generator import hash_report_core
from hash_report_generator.hash_report_combined import CombinedReportGenerator


def _generator():
    logger = logging.getLogger('unreadable-evidence-test')
    logger.disabled = True
    return CombinedReportGenerator(logger, include_ots=False)


class ReadErrorDiagnosisTests(unittest.TestCase):
    def test_cloud_placeholder_is_named(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'placeholder.sqlite'
            path.write_text('x')
            with patch.object(hash_report_core, 'file_attributes', return_value=0x400000):
                info = hash_report_core.describe_read_error(path, OSError(22, 'Invalid argument'))
        self.assertIn('cloud', info['reason'])
        self.assertEqual(info['errno'], 22)

    def test_errno_22_without_cloud_attributes_still_explains_the_read(self):
        info = hash_report_core.describe_read_error('x.bin', OSError(22, 'Invalid argument'))
        self.assertIn('invalid parameter', info['reason'])
        self.assertTrue(info['remedy'])

    def test_locked_file_is_reported_as_in_use(self):
        info = hash_report_core.describe_read_error('x.sqlite-shm', OSError(32, 'in use'))
        self.assertIn('in use', info['reason'])


class DiscoveryFailClosedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / 'readable.txt').write_text('evidence', encoding='utf-8')
        (self.root / 'locked.sqlite-shm').write_bytes(b'x')
        self._env = dict(os.environ)
        os.environ.pop('CHRONOSEAL_ALLOW_UNREADABLE_FILES', None)
        os.environ.pop('CHRONOSEAL_EVIDENCE_DIR', None)
        os.environ.pop('CHRONOSEAL_FOLLOW_LINKS', None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def _fail_on_locked(self, generator):
        real = generator.calculate_sha256

        def calculate(path):
            if Path(path).name == 'locked.sqlite-shm':
                raise OSError(22, 'Invalid argument')
            return real(path)

        return patch.object(generator, 'calculate_sha256', side_effect=calculate)

    def test_unreadable_file_blocks_the_report_by_default(self):
        generator = _generator()
        with self._fail_on_locked(generator):
            with self.assertRaises(RuntimeError) as caught:
                generator._discover_all_files_from_folder(self.root)
        message = str(caught.exception)
        self.assertIn('UNREADABLE_EVIDENCE_FILES', message)
        self.assertIn('locked.sqlite-shm', message)
        self.assertIn('allow_unreadable_files', message)

    def test_operator_opt_in_publishes_with_an_explicit_audit(self):
        with tempfile.TemporaryDirectory() as evidence_dir:
            os.environ['CHRONOSEAL_ALLOW_UNREADABLE_FILES'] = '1'
            os.environ['CHRONOSEAL_EVIDENCE_DIR'] = evidence_dir
            generator = _generator()
            with self._fail_on_locked(generator):
                files = generator._discover_all_files_from_folder(self.root)
            self.assertEqual([item['name'] for item in files], ['readable.txt'])
            audit = json.loads((Path(evidence_dir) / 'discovery-unreadable.json')
                               .read_text(encoding='utf-8'))
        self.assertEqual(audit['unreadable_count'], 1)
        self.assertEqual(audit['unreadable_files'][0]['name'], 'locked.sqlite-shm')
        self.assertIn('errno', audit['unreadable_files'][0])

    def test_standalone_opt_in_writes_the_audit_next_to_the_evidence(self):
        os.environ['CHRONOSEAL_ALLOW_UNREADABLE_FILES'] = '1'
        generator = _generator()
        with self._fail_on_locked(generator):
            generator._discover_all_files_from_folder(self.root)
        audit_path = self.root / 'discovery-unreadable.json'
        self.assertTrue(audit_path.is_file())
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        self.assertEqual(audit['unreadable_count'], 1)
        # The audit itself must never be hashed as evidence on the next run.
        self.assertTrue(generator._is_generated_hash_report(audit_path))
        with self._fail_on_locked(generator):
            names = [item['name'] for item in generator._discover_all_files_from_folder(self.root)]
        self.assertNotIn('discovery-unreadable.json', names)

    def test_readable_folder_still_produces_a_complete_file_list(self):
        generator = _generator()
        (self.root / 'locked.sqlite-shm').unlink()
        files = generator._discover_all_files_from_folder(self.root)
        self.assertEqual([item['name'] for item in files], ['readable.txt'])


class LinkedDirectoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / 'selected'
        self.root.mkdir()
        self.outside = base / 'outside'
        self.outside.mkdir()
        (self.outside / 'secret.txt').write_text('not selected evidence', encoding='utf-8')
        (self.root / 'inside.txt').write_text('selected evidence', encoding='utf-8')
        self._env = dict(os.environ)
        os.environ.pop('CHRONOSEAL_FOLLOW_LINKS', None)
        try:
            os.symlink(self.outside, self.root / 'linked', target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self._tmp.cleanup()
            self.skipTest('directory symlinks are not permitted: ' + str(exc))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def test_linked_directory_is_not_descended_into_by_default(self):
        generator = _generator()
        files = generator._discover_all_files_from_folder(self.root, recursive=True)
        names = [item['name'] for item in files]
        self.assertIn('inside.txt', names)
        self.assertNotIn('linked/secret.txt', names)

    def test_linked_directory_is_followed_only_when_enabled(self):
        os.environ['CHRONOSEAL_FOLLOW_LINKS'] = '1'
        generator = _generator()
        files = generator._discover_all_files_from_folder(self.root, recursive=True)
        names = [item['name'] for item in files]
        self.assertIn('linked/secret.txt', names)


if __name__ == '__main__':
    unittest.main()
