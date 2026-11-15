"""TSA provider selection for independent START / STOP roles.

Given a configured list of TSA providers, this module:
  - returns an ordered START candidate list (preferred provider first);
  - returns an ordered STOP candidate list that excludes the START provider
    (and any other provider IDs the caller wants to skip).

No network calls. No dependency on hash_report_core. Pure selection logic.
"""
from __future__ import annotations

from typing import Iterable, Optional

# Default order follows the v3.7 BRIDGE architecture:
#   START = DFN, STOP = DigiCert (or next independent provider).
DEFAULT_PROVIDERS = [
    {"provider_id": "dfn",        "url": "https://zeitstempel.dfn.de/",
     "priority": 10, "root_sha256": None},
    {"provider_id": "digicert",   "url": "http://timestamp.digicert.com",
     "priority": 20, "root_sha256": None},
    {"provider_id": "globalsign", "url": "http://timestamp.globalsign.com/tsa/r45standard",
     "priority": 30, "root_sha256": None},
    {"provider_id": "sectigo",    "url": "http://timestamp.sectigo.com",
     "priority": 40, "root_sha256": None},
]


def register(api):
    logger = api.get("logger")
    ctx = api.get("context") or {}

    raw = ctx.get("tsaProviders") or DEFAULT_PROVIDERS
    providers = _normalize(raw)

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[helper:tsa_fallback] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    def _pid(p: dict) -> str:
        return str(p.get("provider_id") or "").strip().lower()

    def list_providers() -> list:
        return [dict(p) for p in providers]

    def ids() -> list:
        return [_pid(p) for p in providers]

    def pick_for_start(prefer_ids: Optional[Iterable[str]] = None) -> list:
        """Ordered START candidates. preferred IDs first, then remaining by priority."""
        prefer = [_pid_str(x) for x in (prefer_ids or [])]
        if not prefer:
            return [dict(p) for p in providers]

        preferred = [p for p in providers if _pid(p) in set(prefer)]
        preferred.sort(key=lambda p: prefer.index(_pid(p)))
        rest = [p for p in providers if _pid(p) not in set(prefer)]
        return [dict(p) for p in preferred + rest]

    def pick_for_stop(start_provider_id: str,
                      exclude_ids: Optional[Iterable[str]] = None,
                      prefer_ids: Optional[Iterable[str]] = None) -> list:
        """Ordered STOP candidates, excluding START and any exclude_ids.

        If prefer_ids is given, those (still present after exclusion) move to
        the front in the given order; the rest keep priority order.
        """
        start = _pid_str(start_provider_id)
        exclude = {start}
        if exclude_ids:
            exclude.update(_pid_str(x) for x in exclude_ids)

        remaining = [p for p in providers if _pid(p) not in exclude]

        prefer = [_pid_str(x) for x in (prefer_ids or [])]
        if prefer:
            preferred = [p for p in remaining if _pid(p) in set(prefer)]
            preferred.sort(key=lambda p: prefer.index(_pid(p)))
            rest = [p for p in remaining if _pid(p) not in set(prefer)]
            remaining = preferred + rest

        _log("info", "pick_for_stop",
             start=start, excluded=sorted(exclude),
             candidates=[_pid(p) for p in remaining])
        return [dict(p) for p in remaining]

    def pick_first_stop(start_provider_id: str,
                        exclude_ids: Optional[Iterable[str]] = None,
                        prefer_ids: Optional[Iterable[str]] = None) -> Optional[dict]:
        """Convenience: return the single best STOP candidate or None."""
        candidates = pick_for_stop(start_provider_id,
                                   exclude_ids=exclude_ids,
                                   prefer_ids=prefer_ids)
        return candidates[0] if candidates else None

    _log("info", "initialized", providers=ids())

    return {
        "id": "tsa_fallback",
        "version": "1.0.0",
        "priority": 30,
        "description": "TSA provider selection for independent START/STOP roles",
        "hooks": {},
        "listProviders": list_providers,
        "ids": ids,
        "pickForStart": pick_for_start,
        "pickForStop": pick_for_stop,
        "pickFirstStop": pick_first_stop,
    }


# ---------------------------------------------------------------------------
# helpers (module level, no dependence on register closure)
# ---------------------------------------------------------------------------

def _pid_str(value) -> str:
    return str(value or "").strip().lower()


def _normalize(raw: list) -> list:
    """Sort by (priority, provider_id), drop entries without provider_id, dedupe."""
    cleaned = []
    seen = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        pid = _pid_str(item.get("provider_id"))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        cleaned.append({
            "provider_id": pid,
            "url": str(item.get("url") or "").strip(),
            "priority": int(item.get("priority", 100)),
            "root_sha256": item.get("root_sha256"),
        })
    cleaned.sort(key=lambda p: (p["priority"], p["provider_id"]))
    return cleaned