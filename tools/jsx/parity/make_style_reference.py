#!/usr/bin/env python3
"""Generate the Python-side reference data for the style/policy JavaScript ports.

Run from the repository root:

    python tools/jsx/parity/make_style_reference.py

The reference is produced by the *real* Python modules (style_loader, js_rules,
document_presentation_policy, unified_report_profile, pagination_policy), so the
JavaScript ports are compared against the shipped implementation, not against a
hand-written expectation.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from hash_report_generator import style_loader                                  # noqa: E402
from hash_report_generator import style_runtime                                 # noqa: E402
from hash_report_generator import document_presentation_policy as presentation  # noqa: E402
from hash_report_generator import pagination_policy                             # noqa: E402
from chronoseal import unified_report_profile as profile                        # noqa: E402

DIR_TOKEN = "<DIR>"


def capture(fn):
    """Either {'expect': value} or {'error': 'ValueError: message'}."""
    try:
        return {"expect": fn()}
    except Exception as exc:  # noqa: BLE001 - the message is the contract
        return {"error": type(exc).__name__ + ": " + str(exc)}


def clean(value, token=None):
    if isinstance(value, str):
        return value.replace(str(token), DIR_TOKEN) if token else value
    return value


def write_rules(folder, files):
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(body, encoding="utf-8", newline="\n")


DUPLICATE_FILES = {
    "01_first.js": 'module.exports = {"SAME": 1, "SHARED": {"a": 1}};\n',
    "02_second.js": 'module.exports = {"SAME": 2};\n',
}
NESTED_DUPLICATE_FILES = {
    "01_first.js": 'module.exports = {"PAGE": {"width": 595}};\n',
    "02_second.js": 'module.exports = {"PAGE": {"width": 612}};\n',
}
MERGE_FILES = {
    "01_page.js": 'module.exports = {"PAGE": {"paper": "A4", "width": 595.28}, "COLORS": {"ink": "#111"}};\n',
    "02_more.js": 'module.exports = {"PAGE": {"height": 841.89}, "NESTED": {"list": [1, 2, {"deep": true}]}};\n',
    "03_sub/x_extra.js": 'module.exports = {"EXTRA": {"zero": 0, "flag": false, "text": "\\u00e9"} };\n',
    ".hidden.js": 'module.exports = {"HIDDEN": 1};\n',
    "notes.txt": "not a rule\n",
}
BAD_ROOT_FILES = {"01_array.js": "module.exports = [1, 2, 3];\n"}
THROWING_FILES = {"01_boom.js": 'throw new Error("boom");\n'}

PRESENTATION_FILE_SIZE = [0, 1, 999, 1000, 1234567, 2147483648, -1, 3.9, "42", " 7 ", "5_000", "x", None]
PRESENTATION_DIGEST = ["abcdef", "0123456789abcdef", "ABCDEF", "", "xyz", "ab cd", "ab\n", 123, None]
PRESENTATION_TEXT = ["a\u0301", "\u00c1", "e\u0301cole", "\ufb03", "\u00df", 123, None]
PRESENTATION_FRAGMENT = [0, 1, 2, 3, 4, 10, "3", -1]


def visual_reference():
    values = style_loader.load_styles()["MIGRATED_VISUAL_LITERALS"]
    keys = sorted(values)[:12]
    return [{"key": key, "expect": values[key]} for key in keys]


def layout_reference():
    """layout_rule walks CENTRAL_LAYOUT only; PAGINATION lives at the merged root."""
    root = style_loader.load_styles()["CENTRAL_LAYOUT"]
    return {
        "paths": [
            {"path": ["document_policy"], "expect": style_runtime.layout_rule("document_policy")},
            {"path": ["tables"], "expect": style_runtime.layout_rule("tables")},
            {"path": [], "expect": root},
        ],
        "out_of_scope": {"path": ["PAGINATION"], "error": "KeyError: 'PAGINATION'"},
        "merged_root": {"key": "PAGINATION", "expect": style_loader.load_styles()["PAGINATION"]},
    }


def pagination_reference():
    from reportlab.platypus import Table

    config = pagination_policy.pagination_config()
    keep = []
    # ReportLab refuses a table without rows, so row counts start at 1.
    for rows in range(1, 13):
        table = Table([["r%d" % index] for index in range(rows)])
        keep.append({"rows": rows, **_flowable_kind(
            lambda t=table: pagination_policy.keep_short_section("H", t))})
    return {
        "config": config,
        "keep": keep,
        "heading": _flowable_kind(
            lambda: pagination_policy.keep_heading_with_first_paragraph("H", "P")),
        "non_table": capture(
            lambda: pagination_policy.keep_short_section("H", "not a table")),
    }


def _flowable_kind(fn):
    """Describe what the Python helper returned: one flowable, or a list of them."""
    def describe():
        result = fn()
        if isinstance(result, (list, tuple)):
            return [type(item).__name__ for item in result]
        return [type(result).__name__]
    return capture(describe)


def profile_reference():
    custom = profile.ReportProfile(name="Custom", version="9.9", left_mm=15, min_body_words=30)
    return {
        "default": {
            "to_dict": profile.DEFAULT_PROFILE.to_dict(),
            "audit_options": profile.DEFAULT_PROFILE.audit_options(),
        },
        "custom": {
            "to_dict": custom.to_dict(),
            "audit_options": custom.audit_options(),
        },
    }


def _runner_code(message):
    """Extract the runner's JSON failure code from a js_rules error message.

    js_rules.py forwards the raw stderr payload, so the message is stable only up to
    the last '; '. The code is what identifies the failure.
    """
    tail = message.rsplit('; ', 1)[-1]
    try:
        payload = json.loads(tail)
    except ValueError:
        return None, None
    return payload.get('code'), payload.get('detail')


def loader_cases():
    cases = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        missing = base / "does_not_exist"
        cases["missing_dir"] = capture(
            lambda: style_loader.load_styles(directory=str(missing), pattern="*.js"))

        empty = base / "empty"
        empty.mkdir()
        cases["empty_dir"] = capture(lambda: style_loader.load_styles(directory=str(empty), pattern="*.js"))

        duplicate = base / "duplicate"
        write_rules(duplicate, DUPLICATE_FILES)
        cases["duplicate"] = capture(lambda: style_loader.load_styles(directory=str(duplicate), pattern="*.js"))

        nested = base / "nested_duplicate"
        write_rules(nested, NESTED_DUPLICATE_FILES)
        cases["nested_duplicate"] = capture(
            lambda: style_loader.load_styles(directory=str(nested), pattern="*.js"))

        merge = base / "merge"
        write_rules(merge, MERGE_FILES)
        cases["merge"] = capture(lambda: style_loader.load_styles(directory=str(merge), pattern="*.js"))

        for name, files, token in (
            ("array_root", BAD_ROOT_FILES, "NOT_OBJECT"),
            ("throwing", THROWING_FILES, "EVALUATION"),
        ):
            folder = base / name
            write_rules(folder, files)
            try:
                style_loader.load_styles(directory=str(folder), pattern="*.js")
                cases[name] = {"error": "no error raised"}
            except ValueError as exc:
                code, detail = _runner_code(str(exc))
                cases[name] = {
                    "error_code": code,
                    "expected_code": token,
                    "detail_suffix": clean(detail or "", base),
                    "leaks_subprocess_repr": "Command '" in str(exc),
                }

        cases["missing_sections"] = capture(lambda: style_loader._load(merge, "*.js", None))

        for entry in cases.values():
            if "expect" in entry and isinstance(entry["expect"], str):
                entry["expect"] = clean(entry["expect"], base)
            if "error" in entry:
                entry["error"] = clean(entry["error"], base)
        cases["files"] = {
            "duplicate": DUPLICATE_FILES,
            "nested_duplicate": NESTED_DUPLICATE_FILES,
            "merge": MERGE_FILES,
            "array_root": BAD_ROOT_FILES,
            "throwing": THROWING_FILES,
        }
    return cases


def main():
    styles = style_loader.load_styles()
    payload = {
        "generated_by": "tools/jsx/parity/make_style_reference.py",
        "loader": {
            "required": sorted(style_loader.REQUIRED),
            "sections": sorted(styles),
            "payload": styles,
        },
        "visual": visual_reference(),
        "layout": layout_reference(),
        "presentation": {
            "file_size": [{"input": v, **capture(lambda v=v: presentation.format_file_size(v))}
                          for v in PRESENTATION_FILE_SIZE],
            "digest": [{"input": v, **capture(lambda v=v: presentation.format_digest(v))}
                       for v in PRESENTATION_DIGEST],
            "text": [{"input": v, **capture(lambda v=v: presentation.normalize_text(v))}
                     for v in PRESENTATION_TEXT],
            "fragment": [{"input": v, **capture(lambda v=v: presentation.assert_table_fragment(v))}
                         for v in PRESENTATION_FRAGMENT],
        },
        "profile": profile_reference(),
        "pagination": pagination_reference(),
        "cases": loader_cases(),
    }
    target = ROOT / "tools" / "jsx" / "test" / "fixtures" / "styles.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print("wrote", target, target.stat().st_size, "bytes")


if __name__ == "__main__":
    main()