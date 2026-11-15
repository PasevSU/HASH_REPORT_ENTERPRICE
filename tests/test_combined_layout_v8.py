import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hash_report_generator'))
from hash_report_core import ReportConstants
from combined_table_layout import index_cell, size_kb_cell, digest_cell
from reportlab.lib.styles import getSampleStyleSheet

def test_widths():
    p = ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7
    assert abs(sum(p.values()) - 1) < 1e-9
    assert p['number'] >= .05
    assert p['name'] >= .25

def test_number_unbroken():
    cell = index_cell(155, getSampleStyleSheet()['Normal'])
    assert cell.getPlainText() == '155'

def test_size_and_digest():
    assert size_kb_cell('264.018 KB') == '264.018'
    digest='a1'*32
    cell=digest_cell(digest, getSampleStyleSheet()['Normal'])
    assert cell.getPlainText().replace('\n','') == digest.upper()
