import tempfile
import unittest
from pathlib import Path
from chronoseal.storage_identity import inspect_storage, inspect_workspaces

class StorageIdentityTests(unittest.TestCase):
    def test_existing_directory(self):
        with tempfile.TemporaryDirectory() as d:
            x=inspect_storage(d)
            self.assertEqual(x["probed_directory"],str(Path(d).resolve()))
            self.assertGreater(x["bytes_total"],0)
            self.assertGreaterEqual(x["bytes_available"],0)
            self.assertIsInstance(x["directory_inode_st_ino"],int)
    def test_file_path(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"input.pdf"; f.write_bytes(b"pdf")
            self.assertEqual(inspect_storage(f)["probed_directory"],str(Path(d).resolve()))
    def test_future_evidence_directory(self):
        with tempfile.TemporaryDirectory() as d:
            x=inspect_workspaces(Path(d)/"input.pdf",Path(d)/"future"/"case",d)
            self.assertEqual(set(x),{"input","evidence","output"})
            self.assertEqual(x["evidence"]["probed_directory"],str(Path(d).resolve()))

if __name__=="__main__": unittest.main()
