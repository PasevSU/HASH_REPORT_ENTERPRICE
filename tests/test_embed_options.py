"""The PDF-embedding rules every window shares.

The windows only phrase these answers; the pipeline still decides what is
written. What is pinned here is the prediction the operator reads: which report
type a selection produces, whether the chosen file may be embedded and whether
its pages land before or after the hash report.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chronoseal.embed_options import (  # noqa: E402
    DEFAULT_EMBED_POSITION,
    EmbedOptionError,
    normalise_position,
    report_type_for,
    resolve_embed_options,
    summary_text,
)


def test_position_defaults_to_after_and_accepts_both_sides():
    assert DEFAULT_EMBED_POSITION == "after"
    assert normalise_position("") == "after"
    assert normalise_position(None) == "after"
    assert normalise_position(" Before ") == "before"
    assert normalise_position("AFTER") == "after"


def test_any_other_position_is_refused_in_the_shells_language():
    with pytest.raises(EmbedOptionError) as caught:
        normalise_position("middle", "bg")
    assert caught.value.code == "position"
    assert caught.value.language == "bg"
    assert "преди" in str(caught.value)
    with pytest.raises(EmbedOptionError) as english:
        normalise_position("middle", "en")
    assert "before or after" in str(english.value)
    with pytest.raises(EmbedOptionError) as fallback:
        normalise_position("middle", "de")
    assert fallback.value.language == "en", "unknown languages fall back"


def test_report_type_follows_the_run_shape():
    assert report_type_for(None) == "COMBO"
    assert report_type_for(None, recursive=True) == "COMBO_ALL"
    assert report_type_for(None, single_target=True) == "SINGLE"
    assert report_type_for("single") == "SINGLE_PDF"
    assert report_type_for("combo") == "COMBO_PDF"
    assert report_type_for("combo", recursive=True) == "COMBO_ALL_PDF"


def test_switching_embedding_off_leaves_the_report_type_alone():
    options = resolve_embed_options(
        enabled=False, position="before", path="/does/not/exist.pdf",
        target="/also/missing", recursive=True,
    )
    assert options["enabled"] is False
    assert options["position"] == "before"
    assert options["pdf"] is None and options["source"] is None
    assert options["report_type"] == "COMBO_ALL"


def test_a_folder_target_needs_a_chosen_pdf(tmp_path):
    (tmp_path / "only.pdf").write_bytes(b"%PDF-1.4\n")
    with pytest.raises(EmbedOptionError) as caught:
        resolve_embed_options(enabled=True, path="", target=str(tmp_path))
    assert caught.value.code == "no_pdf"
    # The same folder with a chosen PDF is one folder report, whatever it holds.
    options = resolve_embed_options(enabled=True, path=str(tmp_path / "only.pdf"),
                                    target=str(tmp_path))
    assert options["kind"] == "combo"
    assert options["report_type"] == "COMBO_PDF"


def test_an_explicit_file_list_stays_combo(tmp_path):
    (tmp_path / "only.pdf").write_bytes(b"%PDF-1.4\n")
    options = resolve_embed_options(
        enabled=True, position="before", path=str(tmp_path / "only.pdf"),
        target=str(tmp_path), file_list=True,
    )
    assert options["kind"] == "combo"
    assert options["source_pdf"] is False
    assert options["pdf"] == tmp_path / "only.pdf"
    assert options["report_type"] == "COMBO_PDF"
    recursive = resolve_embed_options(
        enabled=True, path=str(tmp_path / "only.pdf"),
        target=str(tmp_path), file_list=True, recursive=True,
    )
    assert recursive["report_type"] == "COMBO_ALL_PDF"


def test_a_missing_or_non_pdf_choice_is_refused_with_the_path(tmp_path):
    (tmp_path / "notes.txt").write_text("text", encoding="utf-8")
    with pytest.raises(EmbedOptionError) as non_pdf:
        resolve_embed_options(enabled=True, path=str(tmp_path / "notes.txt"),
                              target=str(tmp_path))
    assert non_pdf.value.code == "pdf_invalid"
    assert "notes.txt" in str(non_pdf.value)
    with pytest.raises(EmbedOptionError) as missing:
        resolve_embed_options(enabled=True, path=str(tmp_path / "gone.pdf"),
                              target=str(tmp_path))
    assert missing.value.code == "pdf_invalid"


def test_a_single_input_file_embeds_itself_only_when_it_is_a_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    options = resolve_embed_options(enabled=True, target=str(pdf), path="/ignored.pdf")
    assert options["source_pdf"] is True
    assert options["source"] == pdf
    assert options["pdf"] is None
    assert options["report_type"] == "SINGLE_PDF"
    plain = tmp_path / "report.txt"
    plain.write_text("text", encoding="utf-8")
    with pytest.raises(EmbedOptionError) as caught:
        resolve_embed_options(enabled=True, target=str(plain))
    assert caught.value.code == "single_not_pdf"


def test_the_summary_is_one_readable_line(tmp_path):
    pdf = tmp_path / "Anlage.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    off = resolve_embed_options(enabled=False)
    assert summary_text(off) == "COMBO · no embedded PDF"
    assert summary_text(off, "bg") == "COMBO · PDF не се вгражда"
    on = resolve_embed_options(enabled=True, position="before",
                               path=str(pdf), target=str(tmp_path))
    assert summary_text(on) == "COMBO_PDF · before · Anlage.pdf"
    assert summary_text(on, "bg") == "COMBO_PDF · преди · Anlage.pdf"
