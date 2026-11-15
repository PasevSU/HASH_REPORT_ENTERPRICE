import unittest
from pathlib import Path
from unittest.mock import patch
from chronoseal.startup import ensure_python_dependencies

class EnterpriseStartupTests(unittest.TestCase):
 def test_no_install_if_available(self):
  with patch('chronoseal.startup.importlib.util.find_spec',return_value=object()), patch('chronoseal.startup._run',return_value=(0,'PYTHON_IMPORT_PASS')) as run:
   report=ensure_python_dependencies(Path('.'))
   self.assertFalse(report['blockers'])
   self.assertEqual(len(report['actions']),0)
   self.assertEqual(run.call_count,1)
 def test_missing_dependency_repair_failure_blocks(self):
  with patch('chronoseal.startup.importlib.util.find_spec',return_value=None), patch('chronoseal.startup._run',return_value=(1,'offline')):
   report=ensure_python_dependencies(Path('.'))
   self.assertTrue(report['blockers'])
 def test_missing_dependency_auto_install_disabled_blocks(self):
  with patch('chronoseal.startup.importlib.util.find_spec',return_value=None), patch('chronoseal.startup._run') as run:
   report=ensure_python_dependencies(Path('.'),False)
   self.assertTrue(report['blockers']);run.assert_not_called()
