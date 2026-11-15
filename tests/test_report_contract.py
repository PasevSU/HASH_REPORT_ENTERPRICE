import unittest
from chronoseal.report_contract import COMMON, KIND, inspect_pdf
class ContractTest(unittest.TestCase):
    def test_unique_section_keys(self):
        for kind, extra in KIND.items():
            keys = [x.key for x in (*COMMON,*extra)]
            self.assertEqual(len(keys),len(set(keys)),kind)
    def test_invalid_type(self):
        with self.assertRaises(ValueError):
            inspect_pdf('not-used.pdf','unknown')
if __name__ == '__main__': unittest.main()
