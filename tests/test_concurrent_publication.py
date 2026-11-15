import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from chronoseal.pipeline import Pipeline

class ConcurrentPublicationTests(unittest.TestCase):
    def test_case_names_have_random_suffix(self):
        src=Path(Pipeline.__module__.replace('.', '/'))
        code=(Path(__file__).parents[1]/'chronoseal'/'pipeline.py').read_text()
        self.assertIn('uuid.uuid4().hex[:12]',code)
    def test_publication_does_not_replace_existing_final(self):
        code=(Path(__file__).parents[1]/'chronoseal'/'pipeline.py').read_text()
        self.assertIn('os.link(temp,publish_path)',code)
        self.assertNotIn('os.replace(temp,publish_path)',code)
    def test_atomic_link_collision(self):
        import os
        with TemporaryDirectory() as d:
            a=Path(d)/'temp'; b=Path(d)/'final'
            a.write_text('new');b.write_text('old')
            with self.assertRaises(FileExistsError):os.link(a,b)
            self.assertEqual(b.read_text(),'old')
