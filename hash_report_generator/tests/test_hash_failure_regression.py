import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hash_report_generator.hash_report_single import SingleReportGenerator


class HashFailureTests(unittest.TestCase):
    def setUp(self):
        self.gen = SingleReportGenerator(logging.getLogger('hash-failure-test'))
        self.gen.logger.disabled = True

    def test_missing_file_raises_not_error_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                self.gen.calculate_sha256(Path(tmp) / 'missing.bin')

    def test_get_file_info_fails_explicitly_on_hash_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'a.txt'
            f.write_text('x')
            with patch.object(self.gen, 'calculate_sha256', side_effect=OSError('boom')):
                self.assertIsNone(self.gen.get_file_info(f))

    def test_file_change_during_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'a.txt'
            f.write_text('x')
            real_open = open

            class MutatingFile:
                def __init__(self, handle):
                    self._h = handle
                    self._done = False

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    self._h.close()

                def fileno(self):
                    return self._h.fileno()

                def read(self, n):
                    data = self._h.read(n)
                    if not self._done:
                        self._done = True
                        with real_open(f, 'ab') as w:
                            w.write(b'more')
                    return data

            def mutating_open(*a, **k):
                return MutatingFile(real_open(*a, **k))

            with patch.dict(SingleReportGenerator.calculate_sha256.__globals__, {'open': mutating_open}):
                with self.assertRaises(RuntimeError):
                    self.gen.calculate_sha256(f)

    def test_file_info_reads_times_once_and_hash_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'a.txt'
            f.write_text('abc')
            with patch.object(self.gen, '_get_file_times',
                              wraps=self.gen._get_file_times) as spy:
                info = self.gen.get_file_info(f)
            self.assertEqual(spy.call_count, 1)
            self.assertEqual(len(info['hash']), 64)
            self.assertEqual(info['size'], 3)


if __name__ == '__main__':
    unittest.main()
