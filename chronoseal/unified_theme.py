"""Compatibility facade: the canonical PDF rules are in hash_report_generator/pdf_object_rules.py."""
import sys
from pathlib import Path
from dataclasses import dataclass
_root = Path(__file__).resolve().parents[1] / "hash_report_generator"
if str(_root) not in sys.path: sys.path.insert(0,str(_root))
from pdf_object_rules import PAGE, COLORS, FONTS, LEADING, css_text as _canonical_css
REPORT_KINDS = ("single", "combo", "combo_all", "single_pdf", "combo_pdf", "combo_all_pdf",
                "volume", "automation", "verification")
@dataclass(frozen=True)
class Theme:
    page_width_mm:int=PAGE["width_mm"]
    page_height_mm:int=PAGE["height_mm"]
    margin_left_mm:int=PAGE["left_mm"]
    margin_right_mm:int=PAGE["right_mm"]
    margin_top_mm:int=PAGE["top_mm"]
    margin_bottom_mm:int=PAGE["bottom_mm"]
    footer_reserved_mm:int=PAGE["footer_reserved_mm"]
    body_pt:float=FONTS["body"]
    leading_pt:float=LEADING["body"]
    legal_pt:float=FONTS["legal"]
    heading_pt:float=FONTS["heading"]
    ink:str=COLORS["ink"]
    accent:str=COLORS["accent"]
    muted:str=COLORS["muted"]
    rule:str=COLORS["grid"]
    def validate(self):
        # An assert would silently vanish under `python -O`, leaving the layout
        # invariant unenforced in exactly the runs that skip assertions.
        if self.margin_left_mm+self.margin_right_mm>=self.page_width_mm:
            raise ValueError('Left and right margins must leave a printable body width')
        return self
THEME=Theme().validate()
def report_style(kind):
    if kind not in REPORT_KINDS: raise ValueError(f"Unknown report kind: {kind}")
    return {"kind":kind,"theme":THEME,"same_visual_language":True}
def css_text(theme=THEME): return _canonical_css()
def write_css(path):
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(css_text(),encoding="utf-8");return dest
