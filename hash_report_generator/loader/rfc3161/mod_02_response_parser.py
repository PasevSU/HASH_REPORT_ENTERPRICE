"""Parse an RFC3161 TimeStampResp (DER) using openssl.

Strategy
--------
* Delegates the hard work to `openssl ts -reply -text` (already a project
  dependency).
* Extracts the embedded TimeStampToken with `openssl ts -reply -token_out`.
* Provides structured fields (PKIStatus, genTime, nonce, imprint, serial,
  policy, signer CN, signature algorithm) plus raw text for auditing.

No new dependencies. No network calls. Pure parsing.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def _find_openssl() -> Optional[str]:
    found = shutil.which("openssl")
    if found:
        return found
    candidates = [
        r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe",
        r"C:\Program Files\OpenSSL-Win32\bin\openssl.exe",
        r"C:\Program Files\Git\usr\bin\openssl.exe",
        r"C:\Program Files\Git\mingw64\bin\openssl.exe",
        r"C:\Program Files (x86)\Git\usr\bin\openssl.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _parse_text(text: str) -> dict:
    """Extract fields from `openssl ts -reply -text` output."""
    fields = {}
    patterns = {
        "status":          r"^\s*Status:\s*(.+)$",
        "status_string":   r"^\s*Status description:\s*(.+)$",
        "failure_info":    r"^\s*Failure info:\s*(.+)$",
        "policy_oid":      r"^\s*Policy OID:\s*(.+)$",
        "hash_algorithm":  r"^\s*Hash Algorithm:\s*(.+)$",
        "serial_number":   r"^\s*Serial number:\s*(.+)$",
        "gen_time":        r"^\s*Time stamp:\s*(.+)$",
        "nonce":           r"^\s*Nonce:\s*(.+)$",
        "signer":          r"^\s*TSA:\s*(.+)$",
        "signature_alg":   r"^\s*Signature Algorithm:\s*(.+)$",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()

    # Message data (imprint): small hex dump in the report
    m = re.search(
        r"^\s*Message data:\s*$([\s\S]*?)(?=^\s*[A-Za-z][A-Za-z ]*:\s*)",
        text, re.MULTILINE | re.IGNORECASE,
    )
    if m:
        octets = []
        for line in m.group(1).splitlines():
            hm = re.match(r"^\s*[0-9a-fA-F]{4}\s*-\s*(.*)$", line)
            if hm:
                hex_area = re.split(r"\s{2,}", hm.group(1), maxsplit=1)[0]
                octets.extend(re.findall(
                    r"(?<![0-9a-fA-F])[0-9a-fA-F]{2}(?![0-9a-fA-F])",
                    hex_area.replace("-", " "),
                ))
        if octets:
            fields["message_imprint"] = "".join(octets).lower()
    return fields


def _parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    v = value.strip()
    try:
        return int(v, 0)
    except ValueError:
        pass
    try:
        return int(v, 16)
    except ValueError:
        return None


def register(api):
    logger = api.get("logger")
    ctx = api.get("context") or {}
    openssl_path = ctx.get("opensslPath") or _find_openssl()

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[rfc3161:response_parser] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    if not openssl_path:
        _log("warning", "openssl not found; parser will return error")
    else:
        _log("info", "initialized", openssl=openssl_path)

    def parse(tsr_der: bytes) -> dict:
        """Parse TimeStampResp DER bytes.

        Returns dict with:
            ok, status, status_string, failure_info, hash_algorithm,
            message_imprint, gen_time, serial_number, nonce, policy_oid,
            signer, signature_algorithm, token_der, token_sha256,
            tsr_sha256, raw_text, errors
        """
        result = {
            "ok": False,
            "status": None,
            "status_string": None,
            "failure_info": None,
            "hash_algorithm": None,
            "message_imprint": None,
            "gen_time": None,
            "serial_number": None,
            "nonce": None,
            "nonce_int": None,
            "policy_oid": None,
            "signer": None,
            "signature_algorithm": None,
            "token_der": None,
            "token_sha256": None,
            "tsr_sha256": None,
            "tsr_size": len(tsr_der) if tsr_der else 0,
            "raw_text": None,
            "errors": [],
        }

        if not isinstance(tsr_der, (bytes, bytearray)) or not tsr_der:
            result["errors"].append("empty or invalid input")
            return result

        tsr_bytes = bytes(tsr_der)
        result["tsr_sha256"] = hashlib.sha256(tsr_bytes).hexdigest()

        if not openssl_path:
            result["errors"].append("openssl executable not found")
            return result

        with tempfile.TemporaryDirectory(prefix="rfc3161_parse_") as td:
            d = Path(td)
            tsr_path = d / "response.tsr"
            token_path = d / "token.der"
            tsr_path.write_bytes(tsr_bytes)

            # 1) parse -text
            parsed = subprocess.run(
                [openssl_path, "ts", "-reply", "-in", str(tsr_path), "-text"],
                capture_output=True, text=True, timeout=30,
            )
            raw_text = (parsed.stdout or "") + (parsed.stderr or "")
            result["raw_text"] = raw_text
            if parsed.returncode != 0:
                result["errors"].append(f"openssl ts -reply failed: {raw_text.strip()[:200]}")
                return result

            fields = _parse_text(raw_text)
            result.update({
                "status": fields.get("status"),
                "status_string": fields.get("status_string"),
                "failure_info": fields.get("failure_info"),
                "hash_algorithm": fields.get("hash_algorithm"),
                "message_imprint": fields.get("message_imprint"),
                "gen_time": fields.get("gen_time"),
                "serial_number": fields.get("serial_number"),
                "nonce": fields.get("nonce"),
                "policy_oid": fields.get("policy_oid"),
                "signer": fields.get("signer"),
                "signature_algorithm": fields.get("signature_alg"),
            })
            result["nonce_int"] = _parse_int(result["nonce"] or "")

            # 2) extract TimeStampToken
            token_proc = subprocess.run(
                [openssl_path, "ts", "-reply", "-in", str(tsr_path),
                 "-token_out", "-out", str(token_path)],
                capture_output=True, text=True, timeout=30,
            )
            if token_proc.returncode == 0 and token_path.exists() and token_path.stat().st_size > 0:
                token_der = token_path.read_bytes()
                result["token_der"] = token_der
                result["token_sha256"] = hashlib.sha256(token_der).hexdigest()

        # Determine ok
        status = (result["status"] or "").lower()
        result["ok"] = (
            ("granted" in status) and
            result["token_der"] is not None and
            not result["errors"]
        )
        return result

    def status_ok(parsed: dict) -> bool:
        return bool(parsed and parsed.get("ok"))

    return {
        "id": "response_parser",
        "version": "1.0.0",
        "priority": 20,
        "description": "RFC3161 TimeStampResp parser via openssl",
        "hooks": {},
        "parse": parse,
        "statusOk": status_ok,
        "opensslPath": openssl_path,
    }