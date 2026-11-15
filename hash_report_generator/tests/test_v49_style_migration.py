import unittest
from hash_report_generator.style_loader import load_styles
from hash_report_generator.bridge.canvas import _BRIDGE_FOOTER
class MigrationV49(unittest.TestCase):
    def test_legacy_values_preserved(self):
        rules=load_styles(); self.assertEqual(rules["LEGACY_SPACING_PT"]["bridge__layout__L255"],10)
    def test_bridge_canvas_central(self):
        self.assertEqual(_BRIDGE_FOOTER["horizontal_inset_mm"],12.5)
        self.assertEqual(_BRIDGE_FOOTER["separator_y_pt"],20)
    def test_single_design_preserved(self):
        x=load_styles()["SINGLE_PRESENTATION"]; self.assertEqual(x["title_font_pt"],14);self.assertEqual(x["title_color"],"#18354D")
    def test_no_numeric_spacer_in_migrated_renderers(self):
        paths=["bridge/layout.py","hash_report_core.py","hash_report_single.py","hash_report_combined.py","bridge/helper_enabled.py","modular_report.py"]
        for rel in paths:
            with self.subTest(path=rel):
                tree=__import__("ast").parse((__import__("pathlib").Path(__file__).parents[1]/rel).read_text(encoding="utf8"))
                for node in __import__("ast").walk(tree):
                    if isinstance(node,__import__("ast").Call) and isinstance(node.func,__import__("ast").Name) and node.func.id=="Spacer" and len(node.args)>1:
                        self.assertFalse(isinstance(node.args[1],__import__("ast").Constant) and type(node.args[1].value) in (int,float), f"{rel}:{node.lineno}")
