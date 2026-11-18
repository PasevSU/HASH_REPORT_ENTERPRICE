"""Certificate chain builder using cert_cache + optional network fetcher.

Given a signer certificate (DER), build an ordered chain:
    signer -> issuer -> ... -> self-signed root

Design
------
* This module NEVER declares trust. It only assembles a chain.
* It NEVER performs network I/O by itself. All fetching is delegated to a
  caller-provided `fetcher(url) -> bytes` callback.
* Chain assembly order per step:
    1. Check cert_cache for issuer by AIA CA-Issuers URL.
    2. If not cached and fetcher is provided, download and cache (strict).
    3. If issuer subject == issuer (self-signed), stop.
    4. Repeat up to max_depth levels.

cert_cache is resolved LAZILY at first use:
    1. ctx["certCache"] if provided explicitly, else
    2. parent registry lookup (api["registry"].get("cert_cache"))
"""
from __future__ import annotations

from typing import Callable, Optional

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import (
        AuthorityInformationAccessOID,
        ExtensionOID,
        NameOID,
    )
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


DEFAULT_MAX_DEPTH = 8


def register(api):
    logger = api.get("logger")
    ctx = api.get("context") or {}

    # Lazy resolution: cert_cache may not exist yet at register() time
    # because modules load in alphabetical order.
    _explicit_cache = ctx.get("certCache")
    _parent_registry = api.get("registry")
    _resolved_cache = {"mod": _explicit_cache}

    def _cache_mod():
        if _resolved_cache["mod"] is None and _parent_registry is not None:
            _resolved_cache["mod"] = _parent_registry.get("cert_cache")
        return _resolved_cache["mod"]

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[helper:cert_chain] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    # ---------------- internal helpers ----------------

    def _load_cert(data: bytes):
        for loader in (x509.load_der_x509_certificate,
                       x509.load_pem_x509_certificate):
            try:
                return loader(data)
            except Exception:
                pass
        return None

    def _cn(cert) -> str:
        try:
            values = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            return values[0].value if values else cert.subject.rfc4514_string()
        except Exception:
            return cert.subject.rfc4514_string()

    def _aia_issuer_urls(cert) -> list:
        try:
            aia = cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_INFORMATION_ACCESS
            ).value
        except x509.ExtensionNotFound:
            return []
        urls = []
        for desc in aia:
            if desc.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                loc = desc.access_location
                if isinstance(loc, x509.UniformResourceIdentifier):
                    urls.append(loc.value)
        return urls

    def _is_self_signed(cert) -> bool:
        if cert.subject != cert.issuer:
            return False
        try:
            cert.verify_directly_issued_by(cert)
            return True
        except Exception:
            pass
        try:
            cert.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                cert.signature_algorithm_parameters,
            )
            return True
        except Exception:
            return False

    def _is_issuer_of(child, candidate) -> bool:
        if child.issuer != candidate.subject:
            return False
        try:
            child.verify_directly_issued_by(candidate)
            return True
        except Exception:
            return False

    # ---------------- public API ----------------

    def build(signer_der: bytes, *,
              fetcher: Optional[Callable[[str], bytes]] = None,
              max_depth: int = DEFAULT_MAX_DEPTH,
              allow_expired_cache: bool = True) -> dict:
        """Build ordered chain from signer_der to self-signed root.

        Returns:
            {
              "ok": bool,
              "chain": [ {der, sha256, subject_cn, issuer_cn,
                          subject_rfc4514, issuer_rfc4514,
                          source, url, is_root?}, ... ],
              "depth": int,
              "stopped_reason": str,
              "errors": [str, ...],
            }
        """
        if not CRYPTO_AVAILABLE:
            return {
                "ok": False, "chain": [], "depth": 0,
                "stopped_reason": "cryptography not available",
                "errors": ["cryptography not available"],
            }

        chain = []
        errors = []
        seen_fps = set()
        current_der = bytes(signer_der)
        cache = _cache_mod()

        for depth in range(int(max_depth)):
            cert = _load_cert(current_der)
            if cert is None:
                errors.append(f"depth={depth}: cannot parse certificate")
                return {
                    "ok": False, "chain": chain, "depth": depth,
                    "stopped_reason": "unparseable certificate",
                    "errors": errors,
                }

            fp = cert.fingerprint(hashes.SHA256()).hex()
            if fp in seen_fps:
                return {
                    "ok": True, "chain": chain, "depth": depth,
                    "stopped_reason": "loop detected",
                    "errors": errors,
                }
            seen_fps.add(fp)

            entry = {
                "der": current_der,
                "sha256": fp,
                "subject_cn": _cn(cert),
                "issuer_cn": _cn(cert),
                "subject_rfc4514": cert.subject.rfc4514_string(),
                "issuer_rfc4514": cert.issuer.rfc4514_string(),
                "source": "input" if depth == 0 else "unknown",
                "url": None,
            }
            chain.append(entry)

            if _is_self_signed(cert):
                entry["is_root"] = True
                return {
                    "ok": True, "chain": chain, "depth": depth + 1,
                    "stopped_reason": "self-signed root reached",
                    "errors": errors,
                }

            issuer_urls = _aia_issuer_urls(cert)
            if not issuer_urls:
                return {
                    "ok": False, "chain": chain, "depth": depth + 1,
                    "stopped_reason": "no CA-Issuers URL in AIA extension",
                    "errors": errors,
                }

            issuer_der = None
            issuer_source = None
            issuer_url_used = None

            # 1. try cache
            if cache is not None:
                for url in issuer_urls:
                    cached = cache["get"](url, allow_expired=allow_expired_cache)
                    if cached and cached.get("der"):
                        issuer_der = cached["der"]
                        issuer_source = "cache"
                        issuer_url_used = url
                        _log("info", "issuer from cache", url=url, depth=depth)
                        break

            # 2. try network via fetcher
            if issuer_der is None and fetcher is not None:
                for url in issuer_urls:
                    try:
                        raw = fetcher(url)
                    except Exception as exc:
                        errors.append(f"depth={depth}: fetch failed {url}: {exc}")
                        continue
                    if not raw:
                        errors.append(f"depth={depth}: empty response {url}")
                        continue
                    if cache is not None:
                        try:
                            cache["set"](url, raw,
                                         kind="X509_CA_ISSUER",
                                         source="network",
                                         strict=True)
                        except Exception as exc:
                            errors.append(
                                f"depth={depth}: cache store failed {url}: {exc}"
                            )
                            continue
                    issuer_der = raw
                    issuer_source = "network"
                    issuer_url_used = url
                    _log("info", "issuer from network", url=url, depth=depth)
                    break

            if issuer_der is None:
                return {
                    "ok": False, "chain": chain, "depth": depth + 1,
                    "stopped_reason": "issuer not found in cache and no fetcher",
                    "errors": errors,
                }

            issuer_cert = _load_cert(issuer_der)
            if issuer_cert is None:
                return {
                    "ok": False, "chain": chain, "depth": depth + 1,
                    "stopped_reason": f"issuer unparseable (url={issuer_url_used})",
                    "errors": errors,
                }

            if not _is_issuer_of(cert, issuer_cert):
                errors.append(
                    f"depth={depth}: candidate {_cn(issuer_cert)} is not the issuer of {_cn(cert)}"
                )
                return {
                    "ok": False, "chain": chain, "depth": depth + 1,
                    "stopped_reason": "issuer signature/subject mismatch",
                    "errors": errors,
                }

            # Annotate the *current* entry with where its issuer came from.
            entry["issuer_source"] = issuer_source
            entry["issuer_url"] = issuer_url_used

            current_der = issuer_der

        return {
            "ok": False, "chain": chain, "depth": max_depth,
            "stopped_reason": f"max depth {max_depth} reached",
            "errors": errors,
        }

    def to_summary(result: dict) -> list:
        lines = []
        for i, item in enumerate(result.get("chain") or []):
            if i == 0:
                role = "signer"
            elif item.get("is_root"):
                role = "root"
            else:
                role = "issuer"
            sha = item.get("sha256") or ""
            lines.append(
                f" [{i}] {role:6} | {item.get('subject_cn')} | "
                f"src={item.get('source')} | {sha[:16]}..."
            )
        if result.get("stopped_reason"):
            lines.append(f" stopped: {result['stopped_reason']}")
        if result.get("errors"):
            for err in result["errors"]:
                lines.append(f" error: {err}")
        return lines

    _log("info", "initialized", has_cache=_cache_mod() is not None)

    return {
        "id": "cert_chain",
        "version": "1.0.0",
        "priority": 60,
        "description": "X.509 chain builder (cache + optional fetcher)",
        "hooks": {},
        "build": build,
        "toSummary": to_summary,
    }
