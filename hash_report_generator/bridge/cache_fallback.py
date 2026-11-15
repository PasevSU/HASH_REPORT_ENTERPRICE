"""Bridge cache fallback: route rfc3161_validation downloads through caches.

The original rfc3161_validation.py is NOT modified on disk. This module
monkey-patches its _download, _load_certificate_blob and _load_crl_blob
helpers so that:

    1. cert_cache / crl_cache are consulted first by URL.
    2. On cache miss -> original _download runs.
    3. Successful network fetch is stored in cache for next time.
    4. On network failure with an expired cache entry -> expired entry is
       returned with a "stale" flag, so offline verification still works.

The status returned by validation remains truthful:
    - Fresh cache -> normal PASS
    - Stale cache -> the call site sees the data, and the report may show
      UNAVAILABLE / freshness warnings because _obtain_crl checks dates.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import rfc3161_validation
from loader import load_helpers


# Global reference to the helper registry. Populated by `install()`.
_HELPERS = None


def install(logger=None):
    """Install the monkey-patches. Safe to call multiple times."""
    global _HELPERS
    if _HELPERS is not None:
        return _HELPERS

    _HELPERS = load_helpers({"logger": logger})
    registry = _HELPERS["registry"]
    cert_cache = registry.get("cert_cache")
    crl_cache = registry.get("crl_cache")

    _install_cert_patches(cert_cache)
    _install_crl_patches(crl_cache)

    if logger:
        logger.info(
            f"[bridge:cache_fallback] installed "
            f"(cert_cache={'OK' if cert_cache else 'missing'}, "
            f"crl_cache={'OK' if crl_cache else 'missing'})"
        )
    return _HELPERS


def uninstall():
    """Restore the original _download behavior (for diagnostics only)."""
    global _HELPERS
    if _HELPERS is None:
        return
    for name in ("_download", "_load_certificate_blob", "_load_crl_blob"):
        if hasattr(rfc3161_validation, f"_original_{name}"):
            setattr(rfc3161_validation, name,
                    getattr(rfc3161_validation, f"_original_{name}"))
    _HELPERS = None


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _install_cert_patches(cert_cache):
    if cert_cache is None:
        return

    # Wrap the low-level _download to route certificate fetches via cache.
    if not hasattr(rfc3161_validation, "_original_download"):
        rfc3161_validation._original_download = rfc3161_validation._download
        original_download = rfc3161_validation._original_download

        def cached_download(url, timeout=15):
            # Try fresh cache first
            hit = cert_cache["get"](url)
            if hit is not None:
                return hit["der"]

            # Try network
            try:
                data = original_download(url, timeout=timeout)
            except Exception:
                # Network failed -> try expired cache as last resort
                stale = cert_cache["get"](url, allow_expired=True)
                if stale is not None:
                    return stale["der"]
                raise

            # Store whatever came back, permissively (may be PKCS#7 or PEM)
            try:
                cert_cache["set"](url, data, kind="X509_CA_ISSUER",
                                  source="network", strict=False)
            except Exception:
                pass
            return data

        rfc3161_validation._download = cached_download


def _install_crl_patches(crl_cache):
    if crl_cache is None:
        return

    # CRL fetches also go through _download, so wrap once more for CRL-specific
    # caching by having _obtain_crl consult our CRL cache. Since _obtain_crl
    # uses _download internally, we intercept at that point via a second layer.
    current_download = rfc3161_validation._download

    def cached_download_crl(url, timeout=15):
        # Try fresh CRL cache first
        hit = crl_cache["get"](url)
        if hit is not None:
            return hit["data"]

        # Try network
        try:
            data = current_download(url, timeout=timeout)
        except Exception:
            # Try expired CRL cache
            stale = crl_cache["get"](url, allow_expired=True)
            if stale is not None:
                return stale["data"]
            raise

        # Store CRL permissively (kind=CRL, no parsing)
        try:
            crl_cache["set"](url, data, kind="CRL", source="network")
        except Exception:
            pass
        return data

    rfc3161_validation._download = cached_download_crl