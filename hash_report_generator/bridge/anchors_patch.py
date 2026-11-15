"""Shared monkey-patch for extended trust anchors.

Imported once per process by bridge.run and bridge.verify. Idempotent.
"""
from __future__ import annotations

from cryptography.hazmat.primitives import hashes

import rfc3161_validation
from bridge.trust_anchors import lookup as anchor_lookup


_installed = False


def install() -> None:
    """Patch rfc3161_validation._root_trust_status once per process."""
    global _installed
    if _installed:
        return

    original = rfc3161_validation._root_trust_status

    def extended(root):
        result, note = original(root)
        if result == "PASS" or root is None:
            return result, note

        try:
            fp = root.fingerprint(hashes.SHA256()).hex().lower()
        except Exception as exc:
            return result, f"{note} (bridge fp error: {exc})"

        name = anchor_lookup(fp)
        if name:
            return "PASS", (
                f"{name} SHA-256 matches bridge extended pin "
                f"({fp[:16]}...)"
            )
        return result, note

    rfc3161_validation._root_trust_status = extended
    _installed = True