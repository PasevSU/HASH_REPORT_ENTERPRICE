import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hash_report_generator.hash_report_combined import CombinedReportGenerator


class CombinedMetadataSnapshotTests(unittest.TestCase):
    def test_folder_discovery_uses_single_stat_snapshot(self):
        gen = CombinedReportGenerator(logging.getLogger('combined-meta-test'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.txt').write_text('abc')
            with patch.object(gen, '_get_file_times',
                              side_effect=AssertionError('separate stat')) as spy:
                files = gen._discover_all_files_from_folder(root)
            self.assertEqual(spy.call_count, 0)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0]['size'], 3)
            self.assertLessEqual(files[0]['created'].timestamp(), files[0]['modified'].timestamp() + 1)

    def test_eml_discovery_uses_single_stat_snapshot(self):
        gen = CombinedReportGenerator(logging.getLogger('combined-meta-test'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            eml = root / 'mail.eml'
            eml.write_text('Subject: x\n\nbody')
            (root / 'mail.eml.json').write_text('{}')
            with patch.object(gen, '_get_file_times',
                              side_effect=AssertionError('separate stat')):
                files = gen._discover_all_files_from_eml_folder(eml)
            self.assertTrue(files)
            for f in files:
                self.assertAlmostEqual(f['modified'].timestamp(),
                                       Path(f['path']).stat().st_mtime, places=3)


if __name__ == '__main__':
    unittest.main()