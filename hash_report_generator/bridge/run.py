"""CLI entry point for the helper-enabled bridge.

Usage:
    py -3.12 -m bridge.run single  "path/to/file"
    py -3.12 -m bridge.run combined "path/to/folder"
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from bridge import anchors_patch
anchors_patch.install()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from bridge.helper_enabled import (
    HelperEnabledSingleReportGenerator,
    HelperEnabledCombinedReportGenerator,
)


def _usage() -> int:
    print("Usage:")
    print('  py -3.12 -m bridge.run single   "path/to/file"')
    print('  py -3.12 -m bridge.run combined "path/to/folder-or-eml"')
    return 2


def _print_bridge_summary(gen) -> None:
    log = gen.helper_call_log()
    print(f"\n=== Bridge helper call log ({len(log)} entries) ===")
    for entry in log:
        print(f"  {entry}")

    summary = gen.bridge_provider_summary()
    print(f"\n=== Bridge provider summary ===")
    print(f"  START provider : {summary['start_provider']}")
    print(f"  STOP  provider : {summary['stop_provider']}")
    print(f"  independent    : {summary['independent']}")


def _run_single(target: Path, logger) -> int:
    gen = HelperEnabledSingleReportGenerator(logger, include_ots=False)
    info = gen.get_file_info(target)
    if not info:
        print(f"ERROR: cannot read file: {target}")
        return 1

    identity = gen._create_report_identity()
    pdf_name = gen._get_report_name(info, "individual", identity)
    out = target.parent / pdf_name

    print(f"Report ID : {identity['report_id']}")
    print(f"Output    : {out.name}")
    print()

    ok = gen.generate(info, str(out), None, True, report_identity=identity)

    _print_bridge_summary(gen)
    print(f"\nResult: {'OK' if ok else 'FAIL'}")
    if ok and out.exists():
        print(f"Report: {out}")
        print(f"Size  : {out.stat().st_size / 1024:.1f} KB")
    return 0 if ok else 1


def _run_combined(target: Path, logger) -> int:
    gen = HelperEnabledCombinedReportGenerator(logger, include_ots=False)

    if target.is_dir():
        print(f"Mode: folder (current-directory-only)")
        result = gen.generate_from_folder(target)
    else:
        print(f"Mode: EML")
        result = gen.generate_from_eml(target)

    _print_bridge_summary(gen)
    print(f"\nResult: {'OK' if result else 'FAIL'}")
    if result:
        print(f"Report: {result}")
    return 0 if result else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        return _usage()

    mode, target_str = argv
    if mode not in ("single", "combined"):
        return _usage()

    target = Path(target_str).expanduser().resolve()
    if not target.exists():
        print(f"ERROR: path not found: {target}")
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("bridge")

    print(f"=== Bridge: {mode} ===")
    print(f"Target: {target}")
    print()

    if mode == "single":
        return _run_single(target, logger)
    return _run_combined(target, logger)


if __name__ == "__main__":
    raise SystemExit(main())