import unittest
from hash_report_generator.document_presentation_policy import format_file_size,format_digest,normalize_text,assert_table_fragment
from hash_report_generator.style_runtime import layout_rule
class DocumentPolicyTests(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(format_file_size(355696),"355 696 bytes")
        self.assertRaises(ValueError,format_file_size,-1)
    def test_upper_hex(self):
        self.assertEqual(format_digest("4d1ad5"),"4D1AD5")
        self.assertRaises(ValueError,format_digest,"not-a-hash")
    def test_unicode(self):
        self.assertEqual(normalize_text("Mu\u0308ller"),"Müller")
    def test_fragment(self):
        self.assertRaises(ValueError,assert_table_fragment,2)
        self.assertTrue(assert_table_fragment,3)
    def test_central_policy(self):
        self.assertEqual(layout_rule("document_policy","minimum_orphan_lines"),3)
if __name__=="__main__": unittest.main()
