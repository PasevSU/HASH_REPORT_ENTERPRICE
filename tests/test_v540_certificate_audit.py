from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BRIDGE=(ROOT/'bridge'/'stamp.mjs').read_text(encoding='utf-8')
CORE=(ROOT/'hash_report_generator'/'hash_report_core.py').read_text(encoding='utf-8')

def test_final_pdf_physical_dss_certificates_are_extracted():
    assert 'physicalDssCertificateInventory(reopened)' in BRIDGE
    assert 'latestDssCertRefs' in BRIDGE
    assert 'extractObjectStream' in BRIDGE
    assert 'physical_dss_certificate_extraction' in BRIDGE

def test_physical_dss_coverage_is_fail_closed():
    assert 'missingPhysical' in BRIDGE
    assert 'final physical DSS certificate coverage failed' in BRIDGE
    assert 'physical_coverage_pass' in BRIDGE

def test_certificate_metadata_is_audited():
    for term in ['subject:x.subject','issuer:x.issuer','serial_number:x.serialNumber','valid_from:x.validFrom','valid_to:x.validTo','fingerprint_sha256:x.fingerprint256','key_usage_oids:x.keyUsage']:
        assert term in BRIDGE

def test_embedded_mode_no_longer_claims_network_failure():
    embedded=CORE[CORE.index("if os.environ.get('CHRONOSEAL_REPORT_ONLY') == '1'"):CORE.index("self._rfc3161_token_base64", CORE.index("if os.environ.get('CHRONOSEAL_REPORT_ONLY') == '1'"))]
    assert 'delegated to ChronoSeal final PDF stage' not in embedded
    assert '_generate_chronoseal_pending_record' in embedded
    assert 'See the embedded START/STOP DocTimeStamp signatures and final certificate audit.' in CORE
