#!/usr/bin/env python3
"""Generate the Python-side reference data used by the JavaScript parity tests.

Run from the repository root:

    python tools/jsx/parity/make_reference.py

The script imports the *Python originals* so the JavaScript ports are compared
against the real implementation, never against a hand-written expectation.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from hash_report_generator import file_filters as ff            # noqa: E402
from hash_report_generator import hash_table_engine as hte      # noqa: E402

FILTER_CASES = [
    # (name, rel_path, filters, case_sensitive_env)
    ("scan_0001.eml.pdf", "invoices/2026/scan_0001.eml.pdf", ["*eml.pdf"], None),
    ("scan_0001.pdf", "invoices/2026/scan_0001.pdf", ["*eml.pdf"], None),
    ("scan_0001.EML.PDF", "Invoices/SCAN_0001.EML.PDF", ["*eml.pdf"], None),
    ("scan_0001.EML.PDF", "Invoices/SCAN_0001.EML.PDF", ["*eml.pdf"], "1"),
    ("report.pdf", "report.pdf", ["*.pdf"], None),
    ("report.pdf", "report.pdf", ["*.PDF"], None),
    ("report.pdf", "report.pdf", ["*.PDF"], "1"),
    ("report.pdf", "report.pdf", ["report"], None),
    ("report.pdf", "report.pdf", ["report.pdf"], None),
    ("report.pdf", "report.pdf", ["re?ort.pdf"], None),
    ("report.pdf", "report.pdf", ["repor[st].pdf"], None),
    ("report.pdf", "report.pdf", ["repor[!s].pdf"], None),
    ("report.pdf", "report.pdf", ["*.txt"], None),
    ("report.txt", "deep/nested/report.txt", ["nested/*"], None),
    ("report.txt", "deep/nested/report.txt", ["*nested*"], None),
    ("report.txt", "deep/nested/report.txt", ["deep/*/report.txt"], None),
    ("report.txt", "deep/nested/report.txt", ["*"], None),
    ("report.txt", "deep/nested/report.txt", [], None),
    ("report.txt", "deep/nested/report.txt", ["*.pdf", "*.txt"], None),
    ("report.txt", "deep/nested/report.txt", ["*.pdf", "*.txt"], "1"),
    ("a.pdf", "", ["*.pdf"], None),
    ("", "deep/a.pdf", ["*.pdf"], None),
    ("a.b.c.pdf", "x/a.b.c.pdf", ["*.pdf"], None),
    ("a.b.c.pdf", "x/a.b.c.pdf", ["a.b.c.pdf"], None),
    ("a.b.c.pdf", "x/a.b.c.pdf", ["a.b.c"], None),
    ("a.pdf", "x/a.pdf", ["["], None),
    ("a[1].pdf", "x/a[1].pdf", ["a[[]1].pdf"], None),
    ("a1.pdf", "x/a1.pdf", ["a[0-9].pdf"], None),
    ("a1.pdf", "x/a1.pdf", ["a[!0-9].pdf"], None),
    ("a$.pdf", "x/a$.pdf", ["a$.pdf"], None),
    ("a$.pdf", "x/a$.pdf", ["a$*.pdf"], None),
    ("a b.pdf", "x/a b.pdf", ["a b.pdf"], None),
    ("празен.pdf", "папка/празен.pdf", ["*.pdf"], None),
    ("празен.pdf", "папка/празен.pdf", ["ПРАЗЕН.PDF"], None),
    ("празен.pdf", "папка/празен.pdf", ["ПРАЗЕН.PDF"], "1"),
    ("x.pdf", "x.pdf", ["*.pdf", "*.pdf"], None),
    ("x.pdf", "x.pdf", ["*.pdf;*.eml"], None),
    ("x.eml", "x.eml", ["*.pdf;*.eml"], None),
    ("x.eml", "x.eml", ["*.pdf,*.eml"], None),
    ("x.eml", "x.eml", ["  *.eml  "], None),
    ("", "", ["*"], None),
    ("", "", ["*.pdf"], None),
]

PARSE_CASES = [
    None,
    [],
    "*.pdf",
    ["*.pdf", "*.PDF", "*.eml"],
    ["*.pdf; *.eml", "*.txt"],
    "*.pdf, *.eml\r\n*.txt",
    ["", "   ", ";;;"],
    ["x" * 600, "y" * 100],
    ["a" * 4000],
    ["*.pdf\x00"],
]

NORMALIZE_CASES = ["*.pdf, *.eml", "", "   ", ";", "a\\nb", None, "  spaced  ", "x;y,z"]

NOW_NS = [
    0,
    1_000_000_000_000_000_000,
    1_715_000_000_123_456_789,
    1_715_000_000_999_999_999,
    1_600_000_000_000_000_000,
]


def file_filters_reference():
    out = {"matches": [], "parse": [], "normalize": [], "describe": [], "audit": [], "to_env": []}
    previous_case = os.environ.pop(ff.ENV_CASE, None)
    try:
        for name, rel, filters, flag in FILTER_CASES:
            if flag is None:
                os.environ.pop(ff.ENV_CASE, None)
            else:
                os.environ[ff.ENV_CASE] = flag
            out["matches"].append({
                "name": name, "rel": rel, "filters": filters, "env_case": flag,
                "expect": ff.matches(name, rel, filters),
            })
        os.environ.pop(ff.ENV_CASE, None)
        for value in PARSE_CASES:
            out["parse"].append({"input": value, "expect": ff.parse(value)})
        for value in NORMALIZE_CASES:
            out["normalize"].append({"input": value, "expect": ff.normalize(value)})
        for value in PARSE_CASES:
            out["describe"].append({"input": value, "expect": ff.describe(value)})
        for value in (None, [], ["*.pdf", "*.eml"]):
            out["audit"].append({"input": value, "expect": ff.audit_payload(value)})
        for value in (None, [], ["*.pdf", "*.eml", "*.PDF"]):
            out["to_env"].append({"input": value, "expect": ff.to_env(value)})
    finally:
        if previous_case is None:
            os.environ.pop(ff.ENV_CASE, None)
        else:
            os.environ[ff.ENV_CASE] = previous_case
    return out


CORPUS = {
    "a.txt": "alpha\n",
    "b.PDF": "bravo\n",
    "c.eml.pdf": "charlie\n",
    "empty.bin": "",
    "sub/d.md": "delta\n",
    "sub/nested/e.PDF": "echo\n",
    "sub/nested/deep/f.log": "foxtrot\n",
    "sub/g.json": '{"g": 7}\n',
}


def build_corpus(base):
    for rel, text in CORPUS.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    # deterministic timestamps so the reference dates are reproducible
    stamp = 1_715_000_000
    for rel in CORPUS:
        os.utime(base / rel, (stamp, stamp))


def hash_reference():
    out = {"modes": [], "rows": [], "dates": []}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "corpus"
        base.mkdir()
        build_corpus(base)
        for mode in hte.MODES:
            source = base / "sub" if mode != "single_file" else base / "sub" / "d.md"
            root, files = hte.collect_files(source, mode)
            out["modes"].append({
                "mode": mode,
                "source": source.relative_to(base).as_posix(),
                "root": root.name,
                "files": [p.relative_to(root).as_posix() for p in files],
            })
        rows = hte.build_rows(base, "recursive_folder", algorithms=("sha256", "sha512", "sha1", "md5"))
        out["rows"] = [
            {k: row[k] for k in ("index", "path", "type", "size_bytes", "sha256", "sha512", "sha1", "md5")}
            for row in rows
        ]
        single = hte.build_rows(base / "sub" / "d.md", "single_file")
        out["single"] = [{k: row[k] for k in ("index", "path", "type", "size_bytes", "sha256")} for row in single]
        out["exclude"] = [
            p.relative_to(base).as_posix()
            for p in hte.collect_files(base, "recursive_folder",
                                       exclude=[base / "sub" / "d.md"])[1]
        ]
    for ns in NOW_NS:
        out["dates"].append({
            "ns": ns,
            "expect": hte._date(ns / 1_000_000_000),
        })
    out["corpus"] = CORPUS
    return out


def main():
    payload = {
        "generated_by": "tools/jsx/parity/make_reference.py",
        "file_filters": file_filters_reference(),
        "hash_table": hash_reference(),
    }
    target = ROOT / "tools" / "jsx" / "test" / "fixtures" / "parity.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print("wrote", target, target.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
