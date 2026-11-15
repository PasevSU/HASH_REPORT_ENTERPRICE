from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = (ROOT / "bridge" / "stamp.mjs").read_text(encoding="utf-8")

def test_openssl_ts_verify_uses_token_as_in_and_pdf_byterange_as_data():
    assert "['ts','-verify','-token_in','-in',token,'-data',data,'-CAfile',ca]" in BRIDGE
    assert "['ts','-verify','-token_in','-in',data,'-CAfile',ca]" not in BRIDGE

def test_openssl_inputs_are_written_separately():
    assert "await fs.writeFile(token,raw.token)" in BRIDGE
    assert "await fs.writeFile(data,raw.signed)" in BRIDGE

def test_final_reopen_reuses_independent_openssl_verifier():
    assert "const v=await opensslVerifyRaw(raw,ap.provider)" in BRIDGE

def test_library_extractor_semantic_verification_is_mandatory():
    assert "library_extractor:extractor" in BRIDGE
    assert "library_extractor:finalExtractor" in BRIDGE
    assert "verifyExtractedMandatory" in BRIDGE and "library_extractor_semantic:'MANDATORY'" in BRIDGE

def test_untrusted_bundle_includes_intermediates_and_embedded_signer_material():
    assert "...(provider.intermediate_certificate_files||[]),...(provider.embed_certificate_files||[])" in BRIDGE
