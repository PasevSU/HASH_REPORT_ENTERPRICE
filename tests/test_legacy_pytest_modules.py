"""Run the pytest-style assertion modules inside the unittest release gate.

``npm test``/``npm run verify`` use ``unittest`` discovery, which only collects
``TestCase`` subclasses. The modules listed below are written as plain
``test_*`` functions, so the gate silently executed none of them. This shim
wraps every zero-argument test function in a dynamic TestCase, keeping the
original pytest compatibility while making the release gate actually run them.
"""
import importlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

MODULES = (
    'test_central_table_rules_v16',
    'test_combined_layout_v8',
    'test_explicit_file_selection_source',
    'test_gui_windows_editing',
    'test_no_hardcoded_style',
    'test_v17_shared_layout',
    'test_v536_openssl_semantics',
    'test_v539_report_declaration',
    'test_v540_certificate_audit',
)


def _make_case(module_name):
    module = importlib.import_module(module_name)
    tests = {}
    for name in sorted(dir(module)):
        function = getattr(module, name)
        if name.startswith('test_') and callable(function):
            # Bind the function per iteration; never capture the loop variable.
            tests[name] = (lambda fn: lambda self: fn())(function)
    return type('Test_' + module_name, (unittest.TestCase,), tests)


for _module_name in MODULES:
    globals()['Test_' + _module_name] = _make_case(_module_name)


if __name__ == '__main__':
    unittest.main()
