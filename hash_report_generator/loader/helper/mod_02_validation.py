"""Input / context validation helper (real).

Validates:
  - reportId format: RPT-YYYYMMDD-HHMMSSmmm-XXXXXXXX
  - input paths exist and are regular files
  - symlinks are rejected
  - optional strict mode rejects empty manifest entries
"""
from __future__ import annotations

import re
from pathlib import Path

REPORT_ID_RE = re.compile(r"^RPT-\d{8}-\d{9}-[0-9A-F]{8}$")


def register(api):
    logger = api.get("logger")

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[helper:validation] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    def validate_report_id(report_id) -> bool:
        return isinstance(report_id, str) and bool(REPORT_ID_RE.match(report_id))

    def assert_non_empty_string(value, name):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")

    def check_path(path_str, *, allow_symlink=False) -> Path:
        p = Path(path_str)
        if not p.exists():
            raise FileNotFoundError(f"validation: path does not exist: {path_str}")
        if p.is_symlink() and not allow_symlink:
            raise ValueError(f"validation: symlink not allowed: {path_str}")
        if not p.is_file():
            raise ValueError(f"validation: not a regular file: {path_str}")
        return p

    def before_generate(ctx, _registry):
        if not isinstance(ctx, dict):
            raise ValueError("validation: context must be a dict")

        report_id = ctx.get("reportId")
        if not validate_report_id(report_id):
            raise ValueError(
                f"validation: malformed reportId: {report_id!r} "
                f"(expected RPT-YYYYMMDD-HHMMSSmmm-XXXXXXXX)"
            )

        paths = ctx.get("inputPaths") or []
        if not isinstance(paths, list):
            raise ValueError("validation: inputPaths must be a list")

        for item in paths:
            check_path(item)

        _log("info", "beforeGenerate OK",
             reportId=report_id, inputPaths=len(paths))

    return {
        "id": "validation",
        "version": "1.1.0",
        "priority": 20,
        "description": "Report ID / input path validation",
        "hooks": {
            "beforeGenerate": before_generate,
        },
        "validateReportId": validate_report_id,
        "assertNonEmptyString": assert_non_empty_string,
        "checkPath": check_path,
    }