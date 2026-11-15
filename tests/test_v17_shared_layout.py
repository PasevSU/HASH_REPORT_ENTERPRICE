import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"hash_report_generator"))
from pdf_object_rules import report_title_flowables, legal_qr_box_style, legal_qr_layout_style
from reportlab.platypus import TableStyle

def test_shared_title():
    flow = report_title_flowables(450)
    assert len(flow)==5
    assert [p.style.fontSize for p in flow[:3]]==[14,20,11]

def test_shared_panels():
    assert isinstance(legal_qr_box_style(),TableStyle)
    assert isinstance(legal_qr_layout_style(),TableStyle)

def test_both_generators_consume_shared_rules():
    root=Path(__file__).resolve().parents[1]/"hash_report_generator"
    for name in ("hash_report_single.py","hash_report_combined.py"):
        s=(root/name).read_text(encoding="utf-8")
        assert "from hash_report_core import (" in s
        assert "from hash_report_generator.a4_document import A4DocTemplate" in s
