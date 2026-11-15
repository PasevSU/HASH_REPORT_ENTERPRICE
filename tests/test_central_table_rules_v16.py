import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hash_report_generator"))
from pdf_object_rules import reportlab_table_style, normalize_table_header_paragraphs, COLORS
from reportlab.platypus import Table, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

def test_all_variants():
    for kind in ("standard", "explanatory", "ots", "combined", "hashes", "certificate", "timestamp"):
        assert reportlab_table_style(kind).getCommands()

def test_invalid_variant():
    try: reportlab_table_style("invalid")
    except ValueError: pass
    else: assert False

def test_paragraph_header_is_white():
    p = Paragraph("File Name", getSampleStyleSheet()["Normal"])
    table = Table([[p], ["example"]])
    normalize_table_header_paragraphs(table)
    assert table._cellvalues[0][0].style.textColor.hexval().lower().endswith("ffffff")
