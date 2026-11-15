"""Disk-based cache for X.509 certificates fetched via AIA / CA Issuers.

Layout under CACHE_ROOT:
    <sha256(url)>.meta.json    -> {url, sha256, size, subject_cn, issuer_cn,
                                   serial, not_before, not_after, kind, source,
                                   fetched_at, expires_at}
    <sha256(url)>.der          -> raw certificate bytes (DER, always)

Design notes
------------
* Certificates are stored as DER regardless of input encoding (PEM or DER).
* Metadata is extracted with `cryptography`; if extraction fails, the file is
  still stored but flagged as 'parse_error'.
* Atomic writes: write .tmp -> os.replace.
* Cache lives OUTSIDE the evidence tree and is excluded from package hashing.
* Lookup helpers by URL, by SHA-256 fingerprint (dedup), and by subject CN.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days (certs change rarely)
DEFAULT_CACHE_DIR = Path(".cache") / "certs"


def _sha256_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _utc_now() -> float:
    return time.time()


def _try_parse_cert(der_bytes: bytes) -> dict:
    """Best-effort X.509 metadata extraction. Never raises."""
    info = {
        "subject_cn": None,
        "issuer_cn": None,
        "serial": None,
        "not_before": None,
        "not_after": None,
        "subject_rfc4514": None,
        "issuer_rfc4514": None,
        "parse_error": None,
    }
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
    except ImportError as exc:
        info["parse_error"] = f"cryptography not available: {exc}"
        return info

    try:
        cert = x509.load_der_x509_certificate(der_bytes)
    except Exception:
        try:
            cert = x509.load_pem_x509_certificate(der_bytes)
        except Exception as exc:
            info["parse_error"] = f"not a DER/PEM certificate: {exc}"
            return info

    try:
        subj_cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        info["subject_cn"] = subj_cn[0].value if subj_cn else None
        iss_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        info["issuer_cn"] = iss_cn[0].value if iss_cn else None
        info["serial"] = format(cert.serial_number, "X")
        info["not_before"] = cert.not_valid_before_utc.isoformat()
        info["not_after"] = cert.not_valid_after_utc.isoformat()
        info["subject_rfc4514"] = cert.subject.rfc4514_string()
        info["issuer_rfc4514"] = cert.issuer.rfc4514_string()
    except Exception as exc:
        info["parse_error"] = f"metadata extraction failed: {exc}"
    return info


def _normalize_to_der(data: bytes) -> bytes:
    """Return DER bytes regardless of input being DER or PEM. Raises on failure."""
    if b"-----BEGIN CERTIFICATE-----" in data[:128]:
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            cert = x509.load_pem_x509_certificate(data)
            return cert.public_bytes(serialization.Encoding.DER)
        except Exception as exc:
            raise ValueError(f"PEM certificate parse failed: {exc}") from exc
    return bytes(data)


def register(api):
    logger = api.get("logger")
    ctx = api.get("context") or {}

    base_dir = Path(ctx.get("cacheDir") or DEFAULT_CACHE_DIR)
    base_dir.mkdir(parents=True, exist_ok=True)

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[helper:cert_cache] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    def _paths(url: str):
        key = _sha256_url(url)
        return (
            base_dir / f"{key}.meta.json",
            base_dir / f"{key}.der",
        )

    def _read_meta(meta_path: Path) -> Optional[dict]:
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def get(url: str, *, allow_expired: bool = False) -> Optional[dict]:
        meta_path, der_path = _paths(url)
        if not meta_path.exists() or not der_path.exists():
            return None

        meta = _read_meta(meta_path)
        if not meta:
            return None

        expires_at = float(meta.get("expires_at") or 0.0)
        if not allow_expired and expires_at and _utc_now() > expires_at:
            _log("info", "expired", url=url, expires_at=expires_at)
            return None

        try:
            data = der_path.read_bytes()
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
            "der": data,
            "meta": meta,
            "subject_cn": meta.get("subject_cn"),
            "issuer_cn": meta.get("issuer_cn"),
            "serial": meta.get("serial"),
            "not_before": meta.get("not_before"),
            "not_after": meta.get("not_after"),
            "parse_error": meta.get("parse_error"),
        }

    def set_(url: str, data: bytes, *,
             kind: str = "X509_CA_ISSUER",
             source: str = "network",
             ttl_seconds: int = DEFAULT_TTL_SECONDS,
             meta: Optional[dict] = None,
             strict: bool = False) -> dict:
        """Store certificate bytes.

        strict=False (default): store even if X.509 parse fails, flag parse_error.
        strict=True:            raise ValueError if X.509 parse fails.
        """
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("cert_cache.set: data must be non-empty bytes")

        try:
            der = _normalize_to_der(bytes(data))
        except ValueError as exc:
            raise ValueError(f"cert_cache.set: {exc}") from exc

        cert_info = _try_parse_cert(der)
        if strict and cert_info.get("parse_error"):
            raise ValueError(
                f"cert_cache.set: {cert_info['parse_error']} (strict mode)"
            )

        meta_path, der_path = _paths(url)
        now = _utc_now()

        record = {
            "url": url,
            "sha256": hashlib.sha256(der).hexdigest(),
            "size": len(der),
            "kind": kind,
            "source": source,
            "fetched_at": now,
            "expires_at": now + int(ttl_seconds),
            **cert_info,
        }
        if meta:
            record.update(meta)

        tmp_der = der_path.with_suffix(".der.tmp")
        tmp_meta = meta_path.with_suffix(".meta.json.tmp")
        try:
            tmp_der.write_bytes(der)
            tmp_meta.write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp_der, der_path)
            os.replace(tmp_meta, meta_path)
        finally:
            for tmp in (tmp_der, tmp_meta):
                try:
                    if tmp.exists():
                        tmp.unlink()
                except OSError:
                    pass

        _log("info", "stored", url=url, kind=kind,
             subject_cn=cert_info.get("subject_cn"), size=len(der))
        return record

    def has(url: str, *, allow_expired: bool = False) -> bool:
        return get(url, allow_expired=allow_expired) is not None

    def list_by_subject_cn(cn_substring: str) -> list:
        needle = str(cn_substring or "").strip().lower()
        if not needle:
            return []
        hits = []
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            cn = str(meta.get("subject_cn") or "").lower()
            if needle in cn:
                hits.append({
                    "url": meta.get("url"),
                    "sha256": meta.get("sha256"),
                    "subject_cn": meta.get("subject_cn"),
                    "issuer_cn": meta.get("issuer_cn"),
                })
        return hits

    def find_by_sha256(fingerprint: str) -> Optional[dict]:
        needle = str(fingerprint or "").strip().lower()
        if not needle:
            return None
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            if str(meta.get("sha256") or "").lower() == needle:
                return {
                    "url": meta.get("url"),
                    "sha256": meta.get("sha256"),
                    "subject_cn": meta.get("subject_cn"),
                    "issuer_cn": meta.get("issuer_cn"),
                }
        return None

    def purge_expired() -> int:
        removed = 0
        now = _utc_now()
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            if float(meta.get("expires_at") or 0.0) < now:
                key = meta_path.stem.replace(".meta", "")
                for p in (base_dir / f"{key}.meta.json", base_dir / f"{key}.der"):
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
        items = []
        now = _utc_now()
        total_bytes = 0
        for meta_path in base_dir.glob("*.meta.json"):
            meta = _read_meta(meta_path)
            if not meta:
                continue
            size = int(meta.get("size") or 0)
            total_bytes += size
            items.append({
                "url": meta.get("url"),
                "sha256": meta.get("sha256"),
                "size": size,
                "subject_cn": meta.get("subject_cn"),
                "issuer_cn": meta.get("issuer_cn"),
                "expired": float(meta.get("expires_at") or 0.0) < now,
                "parse_error": meta.get("parse_error"),
            })
        return {
            "cache_dir": str(base_dir.resolve()),
            "entries": len(items),
            "total_bytes": total_bytes,
            "items": items,
        }

    _log("info", "initialized", cache_dir=str(base_dir.resolve()))

    return {
        "id": "cert_cache",
        "version": "1.0.0",
        "priority": 50,
        "description": "Disk-based X.509 certificate cache for AIA / CA Issuers",
        "hooks": {},
        "get": get,
        "set": set_,
        "has": has,
        "findBySha256": find_by_sha256,
        "listBySubjectCn": list_by_subject_cn,
        "purgeExpired": purge_expired,
        "clear": clear,
        "stats": stats,
    }