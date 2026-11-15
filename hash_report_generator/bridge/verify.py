"""Bridge verification: extended trust anchors + cache fallback.

Original files unchanged:
    - rfc3161_validation.py stays on disk as-is; only _root_trust_status and
      _download are monkey-patched at runtime.
    - verify_rfc3161_evidence.py is imported unchanged.

Usage:
    py -3.12 -m bridge.verify "path/to/HASHREPORT.pdf"
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from cryptography.hazmat.primitives import hashes

import rfc3161_validation
from bridge.trust_anchors import lookup as anchor_lookup
from bridge import cache_fallback
from bridge import anchors_patch
anchors_patch.install()


# ---------------------------------------------------------------------------
# monkey-patch 1: extended root trust anchors
# ---------------------------------------------------------------------------
_original_root_trust_status = rfc3161_validation._root_trust_status


def _extended_root_trust_status(root):
    orig_result, orig_note = _original_root_trust_status(root)
    if orig_result == "PASS" or root is None:
        return orig_result, orig_note

    try:
        fp = root.fingerprint(hashes.SHA256()).hex().lower()
    except Exception as exc:
        return orig_result, f"{orig_note} (bridge fp error: {exc})"

    name = anchor_lookup(fp)
    if name:
        return "PASS", (
            f"{name} SHA-256 matches bridge extended pin "
            f"({fp[:16]}...)"
        )
    return orig_result, orig_note


rfc3161_validation._root_trust_status = _extended_root_trust_status


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("Usage:")
        print('  py -3.12 -m bridge.verify "path/to/HASHREPORT.pdf"')
        return 2

    pdf = Path(argv[0]).expanduser().resolve()
    if not pdf.is_file():
        print(f"ERROR: PDF not found: {pdf}")
        return 2

    # Install cache fallback so offline verification works
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger("bridge.verify")
    helpers = cache_fallback.install(logger=logger)
    summary = helpers["summary"]
    pinned = len(anchor_lookup.__globals__.get("EXTENDED_TRUST_ANCHORS", {})) \
        if hasattr(anchor_lookup, "__globals__") else 8

    print(f"=== Bridge verify (extended anchors + cache fallback) ===")
    print(f"PDF: {pdf}")
    print(f"Helpers: {summary.get('modules')}")
    print(f"Extended trust anchors: {pinned} pins")
    print()

    from verify_rfc3161_evidence import main as verify_main

    original_argv = sys.argv
    sys.argv = ["verify_rfc3161_evidence.py", str(pdf)]
    try:
        return verify_main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())