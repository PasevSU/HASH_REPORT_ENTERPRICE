from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CORE=(ROOT/'hash_report_generator'/'hash_report_core.py').read_text(encoding='utf-8')
COMBO=(ROOT/'hash_report_generator'/'hash_report_combined.py').read_text(encoding='utf-8')
SINGLE=(ROOT/'hash_report_generator'/'hash_report_single.py').read_text(encoding='utf-8')

HEADER=(ROOT/'hash_report_generator'/'style'/'73_report_header.js').read_text(encoding='utf-8')

def test_signature_line_removed():
    assert '(Signature / Unterschrift)' not in CORE
    assert '_________________________' not in CORE

def test_certificate_verifiability_text_present():
    assert 'DSS/Certs' in CORE
    assert 'Validate PDF ByteRange, RFC3161 CMS token, TSA chain and DSS/Certs' in CORE
    assert 'Prüfbarkeit und Grenzen' in HEADER
    assert 'Prüfbarkeit und Grenzen' not in SINGLE and 'Prüfbarkeit und Grenzen' not in COMBO

def test_signature_notice_is_narrow_not_legal_overclaim():
    assert 'ein Zeitstempel allein erfüllt diese Voraussetzung nicht.' in HEADER
    assert 'Die Nennung begründet keine Zertifizierung oder Konformität.' in HEADER

def _assert_after_stop(src, combined):
    stop=src.index('self._add_end_timestamp_section(')
    decl=src.index('self._add_legal_declaration(', stop)
    foot=src.index('self._add_footer(', decl)
    assert stop < decl < foot

def test_combo_declaration_after_stop(): _assert_after_stop(COMBO, True)
def test_single_declaration_after_stop(): _assert_after_stop(SINGLE, False)
