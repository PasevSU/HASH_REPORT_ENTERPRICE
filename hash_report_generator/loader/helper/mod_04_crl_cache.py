"""Disk-based cache for CRL / OCSP responses.

Layout under CACHE_ROOT:
    <sha256(url)>.meta.json    -> {url, sha256, size, kind, source, fetched_at, expires_at}
    <sha256(url)>.bin          -> raw bytes

Cache is intentionally outside the evidence tree and excluded from package
hash control. Atomic writes: write .tmp -> rename.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

DEFAULT_TTL_SECONDS = 24 * 3600  # 24h
DEFAULT_CACHE_DIR = Path(".cache") / "crl"


def _sha256_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _utc_now() -> float:
    return time.time()


def register(api):
    logger = api.get("logger")
    ctx = api.get("context") or {}

    base_dir = Path(ctx.get("cacheDir") or DEFAULT_CACHE_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[helper:crl_cache] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    def _paths(url: str):
        key = _sha256_url(url)
        return (
            base_dir / f"{key}.meta.json",
            base_dir / f"{key}.bin",
        )

    def _read_meta(meta_path: Path) -> Optional[dict]:
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def get(url: str, *, allow_expired: bool = False) -> Optional[dict]:
        """Return cached entry {url, sha256, size, data, meta} or None."""
        meta_path, bin_path = _paths(url)
        if not meta_path.exists() or not bin_path.exists():
            return None

        meta = _read_meta(meta_path)
        if not meta:
            return None

        expires_at = float(meta.get("expires_at") or 0.0)
        if not allow_expired and expires_at and _utc_now() > expires_at:
            _log("info", "expired", url=url, expires_at=expires_at)
            return None

        try:
            data = bin_path.read_bytes()
        except OSError as exc:
            _log("warning", "read failed", url=url, error=str(exc))
            return None

        actual = hashlib.sha256(data).hexdigest()
        if actual != meta.get("sha256"):
            _log("warning", "cache corruption detected", url=url)
            return None

        return {
            "url": url,
            "sha256": actual,
            "size": len(data),
            "data": data,
            "meta": meta,
        }

    def set_(url: str, data: bytes, *,
             kind: str = "CRL",
             source: str = "network",
             ttl_seconds: int = DEFAULT_TTL_SECONDS,
             meta: Optional[dict] = None) -> dict:
        """Atomically write entry. Returns metadata actually stored."""
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("crl_cache.set: data must be non-empty bytes")

        data = bytes(data)
        meta_path, bin_path = _paths(url)
        now = _utc_now()
        record = {
            "url": url,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "kind": kind,
            "source": source,
            "fetched_at": now,
            "expires_at": now + int(ttl_seconds),
        }
        if meta:
            record.update(meta)

        tmp_bin = bin_path.with_suffix(".bin.tmp")
        tmp_meta = meta_path.with_suffix(".meta.json.tmp")

        try:
            tmp_bin.write_bytes(data)
            tmp_meta.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_bin, bin_path)
            os.replace(tmp_meta, meta_path)
        finally:
            for tmp in (tmp_bin, tmp_meta):
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass

        _log("info", "stored", url=url, kind=kind, size=len(data))
        return record

    def has(url: str, *, allow_expired: bool = False) -> bool:
        return get(url, allow_expired=allow_expired) is not None

    def purge_expired() -> int:
        removed = 0
        now = _utc_now()
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            if float(meta.get("expires_at") or 0.0) < now:
                key = meta_path.stem.replace(".meta", "")
                for p in (base_dir / f"{key}.meta.json", base_dir / f"{key}.bin"):
                    try:
                        if p.exists():
                            p.unlink()
                            removed += 1
                    except OSError:
                        pass
        _log("info", "purge_expired", removed=removed)
        return removed

    def clear() -> int:
        removed = 0
        for p in base_dir.glob("*"):
            try:
                if p.is_file():
                    p.unlink()
                    removed += 1
            except OSError:
                pass
        _log("info", "clear", removed=removed)
        return removed

    def stats() -> dict:
        entries = []
        now = _utc_now()
        total_bytes = 0
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            size = int(meta.get("size") or 0)
            total_bytes += size
            entries.append({
                "url": meta.get("url"),
                "sha256": meta.get("sha256"),
                "size": size,
                "kind": meta.get("kind"),
                "expired": float(meta.get("expires_at") or 0.0) < now,
            })
        return {
            "cache_dir": str(base_dir.resolve()),
            "entries": len(entries),
            "total_bytes": total_bytes,
            "items": entries,
        }

    _log("info", "initialized", cache_dir=str(base_dir.resolve()))

    return {
        "id": "crl_cache",
        "version": "1.0.0",
        "priority": 40,
        "description": "Disk-based CRL/OCSP cache with TTL and atomic writes",
        "hooks": {},
        "get": get,
        "set": set_,
        "has": has,
        "purgeExpired": purge_expired,
        "clear": clear,
        "stats": stats,
    }