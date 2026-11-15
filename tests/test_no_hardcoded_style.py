"""Enforce that report visuals come only from the central style loaders."""
import re
from pathlib import Path

GEN = Path(__file__).resolve().parents[1] / 'hash_report_generator'
GENERATORS = ['hash_report_single.py', 'hash_report_combined.py', 'report_header.py',
              'modular_report.py', 'bridge/helper_enabled.py']
HEX = re.compile(r"#[0-9a-fA-F]{6}\b|HexColor\(\s*['\"]#")
LOCAL_TABLE_STYLE = re.compile(r"\.setStyle\(\s*TableStyle\(")


def test_generators_have_no_hardcoded_colors():
    for name in GENERATORS:
        text = (GEN / name).read_text(encoding='utf-8')
        assert not HEX.search(text), f'{name} contains a hardcoded colour'


def test_generators_have_no_local_table_style():
    for name in GENERATORS:
        if name == 'report_header.py':
            continue  # central layout module driven by 73_report_header.js
        text = (GEN / name).read_text(encoding='utf-8')
        assert not LOCAL_TABLE_STYLE.search(text), f'{name} styles a table locally'


def test_core_colors_come_from_central_rules():
    text = (GEN / 'hash_report_core.py').read_text(encoding='utf-8')
    assert not HEX.search(text)


def test_status_and_header_rules_exist():
    from hash_report_generator.pdf_object_rules import _STYLE
    assert {'ok', 'error', 'warning', 'primary', 'muted'} <= set(_STYLE['STATUS_COLORS'])
    assert _STYLE['REPORT_HEADER']['legal_html']
