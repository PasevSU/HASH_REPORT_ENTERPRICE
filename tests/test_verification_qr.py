"""The closing verification block: a QR code that leads to the electronic documents.

Two layers are pinned here. ``chronoseal.verification_qr`` is what a window asks
before a run ("is the option on, is the address usable, what do I show in one
line"), and ``hash_report_generator.verification_qr`` is what the stand-alone
generator writes at the physical end of the report. They validate independently
on purpose, so both sides carry their own cases.
"""
import inspect
import json
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.platypus import SimpleDocTemplate

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chronoseal import verification_qr as shell  # noqa: E402
from chronoseal.pipeline import Pipeline  # noqa: E402
from hash_report_generator import verification_qr as generator  # noqa: E402


def _flat(text):
    """PDF extraction breaks lines; compare on collapsed whitespace."""
    return " ".join((text or "").split())


def _render(folder, url, is_combined):
    flowables, rendered = generator.build(url, is_combined=is_combined)
    target = Path(folder) / ("combo.pdf" if is_combined else "single.pdf")
    SimpleDocTemplate(str(target)).build(list(flowables))
    return _flat(PdfReader(str(target)).pages[0].extract_text()), rendered


# --------------------------------------------------------------- shell rules
def test_every_run_gets_a_link_because_the_block_is_mandatory():
    resolved = shell.resolve({}, environ={})
    assert resolved["enabled"] is True
    assert resolved["position"] == shell.QR_POSITION == "document_end"
    assert resolved["url"] == shell.DEFAULT_BASE_URL + resolved["code"]
    assert resolved["code"].count("-") == len(shell.CODE_GROUPS) - 1


def test_the_generated_code_keeps_the_layout_the_document_server_issues():
    code = shell.new_code()
    groups = code.split("-")
    assert [len(group) for group in groups] == list(shell.CODE_GROUPS)
    assert sum(len(group) for group in groups) >= 32
    assert all(character in "0123456789abcdef" for group in groups for character in group)


def test_two_runs_never_share_a_code():
    first = shell.new_link({}, environ={})
    second = shell.new_link({}, environ={})
    assert first["code"] != second["code"]
    assert first["url"] != second["url"]


def test_the_base_address_comes_from_the_environment_then_the_configuration():
    configured = {"verification": {"base_url": "https://configured.example/evidence"}}
    assert shell.base_url(configured, {}) == "https://configured.example/evidence/"
    assert shell.base_url(configured, {shell.BASE_URL_ENV: "http://from-env.example/x/"}) == \
        "http://from-env.example/x/"
    assert shell.base_url({}, {}) == shell.DEFAULT_BASE_URL
    assert shell.DEFAULT_BASE_URL.endswith("/")


def test_a_missing_trailing_slash_is_added_once():
    assert shell.base_url({"verification": {"base_url": "https://example.org/static"}}, {}) == \
        "https://example.org/static/"
    assert shell.base_url({"verification": {"base_url": "https://example.org/static//"}}, {}) == \
        "https://example.org/static//"


def test_an_explicit_override_is_printed_verbatim():
    link = shell.new_link({}, {}, "https://example.org/evidence/abc-123")
    assert link == {"code": "abc-123", "url": "https://example.org/evidence/abc-123"}
    resolved = shell.resolve({}, {}, "https://example.org/evidence/abc-123")
    assert resolved["url"] == "https://example.org/evidence/abc-123"
    assert resolved["code"] == "abc-123"


@pytest.mark.parametrize("value, code", [
    ("ftp://example.org/report", "url_scheme"),
    ("example.org/report", "url_scheme"),
    ("https:///no-host", "url_invalid"),
    ("https://example.org/a b", "url_invalid"),
    ("https://example.org/" + "x" * shell.MAX_URL_LENGTH, "url_too_long"),
])
def test_a_base_that_cannot_resolve_is_refused(value, code):
    with pytest.raises(shell.QrOptionError) as caught:
        shell.base_url({}, {shell.BASE_URL_ENV: value})
    assert caught.value.code == code
    assert caught.value.language == "en"
    assert str(caught.value) == shell.MESSAGES[code]["en"]


def test_the_same_refusals_apply_to_an_explicit_override():
    for value in ("ftp://example.org/x", "example.org/x", "https://"):
        with pytest.raises(shell.QrOptionError):
            shell.resolve({}, {}, value)


def test_code_groups_are_configurable_and_never_too_short():
    assert shell.code_groups({"verification": {"code_groups": [8, 4, 20]}}) == (8, 4, 20)
    code = shell.new_code(shell.code_groups({"verification": {"code_groups": [8, 4, 20]}}))
    assert [len(group) for group in code.split("-")] == [8, 4, 20]
    assert shell.code_groups({"verification": {"code_groups": []}}) == shell.CODE_GROUPS
    with pytest.raises(shell.QrOptionError):
        shell.code_groups({"verification": {"code_groups": [4, 4]}})


def test_both_web_schemes_are_accepted_and_the_address_is_trimmed():
    assert shell.normalise_url("  https://example.org/evidence  ") == "https://example.org/evidence"
    assert shell.normalise_url("http://example.org/") == "http://example.org/"
    assert shell.normalise_url("") == ""


def test_the_summary_names_the_host_and_hides_the_generated_code():
    resolved = shell.resolve({"verification": {"base_url": "https://example.org/evidence"}}, {})
    assert shell.summary_text(resolved) == "QR · example.org/evidence"
    assert shell.summary_text({"url": "https://example.org/"}) == "QR · example.org"
    assert shell.summary_text({}, "bg") == shell.INFO_LABEL["bg"]
    assert shell.summary_text(None, "en") == shell.INFO_LABEL["en"]


# ----------------------------------------------------------- generator rules
def test_the_generator_reads_the_switch_from_its_environment():
    assert generator.from_environment({}) == ""
    assert generator.from_environment({"CHRONOSEAL_VERIFICATION_QR": "0"}) == ""
    # Switch on without an address means "nothing to print", not a crash: the
    # pipeline validates the target before it ever reaches this channel.
    assert generator.from_environment({"CHRONOSEAL_VERIFICATION_QR": "1"}) == ""
    with pytest.raises(generator.VerificationQrError):
        generator.from_environment({"CHRONOSEAL_VERIFICATION_QR": "1",
                                    generator.ENV_URL: "example.org/evidence"})
    for switch in ("1", "true", "YES", "on"):
        environ = {"CHRONOSEAL_VERIFICATION_QR": switch,
                   generator.ENV_URL: "https://example.org/evidence"}
        assert generator.from_environment(environ) == "https://example.org/evidence"


def test_the_generator_refuses_the_same_addresses_as_the_shell():
    assert generator.normalise("") == ""
    assert generator.normalise(None) == ""
    for value in ("ftp://example.org/x", "example.org/x", "https://", "https://example.org/a b"):
        with pytest.raises(generator.VerificationQrError):
            generator.normalise(value)


def test_the_block_is_empty_when_the_switch_is_off():
    story = []
    assert generator.add_section(story, environ={}) == ""
    assert story == []
    assert generator.build("") == ([], False)


def test_the_block_states_whether_one_file_or_an_archive_was_documented(tmp_path):
    pytest.importorskip("qrcode")
    single, rendered = _render(tmp_path, "https://example.org/evidence", is_combined=False)
    combo, _ = _render(tmp_path, "https://example.org/evidence", is_combined=True)
    assert rendered is True
    for text in (single, combo):
        assert "ZIP-Archiv" in text
        assert "RFC-3161" in text
        assert "https://example.org/evidence" in text
        # The caption explains the companion proof and what the link delivers, so a
        # reader who only holds the printed report knows what to expect.
        assert ".ots" in text
        assert "ots verify" in text
        assert "Bitcoin" in text
        assert "liefert den Bericht und die zugehörigen Prüfdateien gemeinsam" in text
    assert "dokumentiert eine Datei" in single
    assert "dokumentiert mehrere Dateien" in combo


def test_the_block_records_the_target_it_reached_the_pdf_with(tmp_path):
    sidecar = generator.record("https://example.org/evidence", is_combined=True,
                               qr_rendered=True,
                               environ={"CHRONOSEAL_EVIDENCE_DIR": str(tmp_path)})
    payload = json.loads(Path(sidecar).read_text(encoding="utf-8"))
    assert sidecar.name == generator.SIDECAR_NAME
    assert payload["schema"] == generator.SCHEMA
    assert payload["url"] == "https://example.org/evidence"
    assert payload["documented_files"] == "multiple"
    assert payload["qr_rendered"] is True
    assert payload["applied_at"]
    assert generator.record("https://example.org/evidence", is_combined=False,
                            qr_rendered=False, environ={}) is None


def test_add_section_extends_the_story_and_returns_the_target(tmp_path):
    story = []
    environ = {"CHRONOSEAL_VERIFICATION_QR": "1",
               generator.ENV_URL: "https://example.org/evidence",
               "CHRONOSEAL_EVIDENCE_DIR": str(tmp_path)}
    assert generator.add_section(story, is_combined=False, environ=environ) == \
        "https://example.org/evidence"
    assert len(story) == 3
    payload = json.loads((tmp_path / generator.SIDECAR_NAME).read_text(encoding="utf-8"))
    assert payload["documented_files"] == "single"


# ---------------------------------------------------------- pipeline contract
def test_the_run_takes_the_target_last_so_old_callers_keep_working():
    run = inspect.signature(Pipeline.run).parameters
    assert list(run)[-1] == "qr_url"
    assert run["qr_url"].default == ""
    assert inspect.signature(Pipeline.generate).parameters["qr_url"].default == ""
