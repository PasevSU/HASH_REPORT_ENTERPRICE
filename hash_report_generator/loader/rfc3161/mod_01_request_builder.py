"""Build RFC3161 TimeStampReq (DER) without external DER dependencies.

Pure Python DER encoder for the minimal request needed by RFC3161:
    TimeStampReq ::= SEQUENCE {
        version        INTEGER { v1(1) },
        messageImprint MessageImprint,
        reqPolicy      TSAPolicyId OPTIONAL,
        nonce          INTEGER OPTIONAL,
        certReq        BOOLEAN DEFAULT FALSE,
        extensions     [0] IMPLICIT Extensions OPTIONAL
    }
    MessageImprint ::= SEQUENCE {
        hashAlgorithm  AlgorithmIdentifier,
        hashedMessage  OCTET STRING
    }

Supported hash algorithms: SHA-256 (default), SHA-1, SHA-384, SHA-512, SHA3-256.
Supported nonce lengths: arbitrary (recommended 64-128 bits).
"""
from __future__ import annotations

import hashlib
import os
from typing import Optional


# ---------------------------------------------------------------------------
# DER primitives
# ---------------------------------------------------------------------------

def _der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(value)) + value


def _seq(*parts: bytes) -> bytes:
    return _tlv(0x30, b"".join(parts))


def _integer(value: int) -> bytes:
    if value < 0:
        raise ValueError("only non-negative integers supported")
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return _tlv(0x02, raw)


def _bool(value: bool) -> bytes:
    return _tlv(0x01, b"\xff" if value else b"\x00")


def _octet_string(data: bytes) -> bytes:
    return _tlv(0x04, data)


def _oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.strip().split(".")]
    if len(parts) < 2:
        raise ValueError(f"OID needs at least 2 components: {dotted}")
    first = 40 * parts[0] + parts[1]
    body = bytes([first])
    for p in parts[2:]:
        if p == 0:
            body += b"\x00"
            continue
        chunk = []
        while p > 0:
            chunk.insert(0, p & 0x7F)
            p >>= 7
        for i in range(len(chunk) - 1):
            chunk[i] |= 0x80
        body += bytes(chunk)
    return _tlv(0x06, body)


# ---------------------------------------------------------------------------
# Hash algorithm OIDs (RFC 8017 / NIST)
# ---------------------------------------------------------------------------

HASH_OIDS = {
    "sha1":     "1.3.14.3.2.26",
    "sha256":   "2.16.840.1.101.3.4.2.1",
    "sha384":   "2.16.840.1.101.3.4.2.2",
    "sha512":   "2.16.840.1.101.3.4.2.3",
    "sha3-256": "2.16.840.1.101.3.4.2.8",
    "sha3-384": "2.16.840.1.101.3.4.2.9",
    "sha3-512": "2.16.840.1.101.3.4.2.10",
}

HASH_CALLABLES = {
    "sha1":     hashlib.sha1,
    "sha256":   hashlib.sha256,
    "sha384":   hashlib.sha384,
    "sha512":   hashlib.sha512,
    "sha3-256": hashlib.sha3_256,
    "sha3-384": hashlib.sha3_384,
    "sha3-512": hashlib.sha3_512,
}


def register(api):
    logger = api.get("logger")

    def _log(level, msg, **extra):
        if not logger:
            return
        line = f"[rfc3161:request_builder] {msg}"
        if extra:
            line += " " + str(extra)
        getattr(logger, level, logger.info)(line)

    def build(message_imprint: bytes, *,
              nonce: Optional[int] = None,
              nonce_bits: int = 128,
              cert_req: bool = True,
              req_policy_oid: Optional[str] = None) -> bytes:
        """Build a TimeStampReq DER for a precomputed message imprint.

        Args:
            message_imprint: raw bytes of the digest (e.g., SHA-256 = 32 bytes)
            nonce: explicit integer nonce. If None, generated from os.urandom.
            nonce_bits: size of auto-generated nonce (default 128).
            cert_req: request TSA to include its certificate (RFC3161 sec 2.4.2)
            req_policy_oid: optional required TSA policy

        Returns:
            DER-encoded TimeStampReq bytes.
        """
        if not isinstance(message_imprint, (bytes, bytearray)) or not message_imprint:
            raise ValueError("message_imprint must be non-empty bytes")
        message_imprint = bytes(message_imprint)

        if nonce is None:
            if nonce_bits <= 0:
                raise ValueError("nonce_bits must be > 0")
            byte_len = (nonce_bits + 7) // 8
            nonce = int.from_bytes(os.urandom(byte_len), "big")

        # TimeStampReq.version = 1
        parts = [_integer(1)]

        # messageImprint uses SHA-256 by default; caller passes the actual digest.
        # We detect the algorithm size to pick a matching OID, but for full
        # control the caller should use build_from_hash().
        alg_name = _guess_hash_name(len(message_imprint))
        alg_oid = HASH_OIDS[alg_name]
        alg_id = _seq(_oid(alg_oid), _tlv(0x05, b""))  # NULL params
        parts.append(_seq(alg_id, _octet_string(message_imprint)))

        if req_policy_oid:
            parts.append(_oid(req_policy_oid))

        parts.append(_integer(nonce))

        if cert_req:
            parts.append(_bool(True))

        request = _seq(*parts)
        _log("info", "built", size=len(request),
             imprint_len=len(message_imprint),
             hash_alg=alg_name, nonce_bits=nonce_bits)
        return request

    def build_from_hash(data: bytes, *, hash_name: str = "sha256",
                        nonce: Optional[int] = None,
                        nonce_bits: int = 128,
                        cert_req: bool = True,
                        req_policy_oid: Optional[str] = None) -> dict:
        """Hash `data` and build the request. Returns {request_der, imprint,
        hash_name, nonce, nonce_bits}.
        """
        key = hash_name.lower().replace("-", "")
        if key not in HASH_CALLABLES:
            raise ValueError(f"unsupported hash: {hash_name}")
        # normalize
        canonical = next(k for k in HASH_CALLABLES if k.replace("-", "") == key)
        digest = HASH_CALLABLES[canonical](data).digest()

        if nonce is None:
            byte_len = (nonce_bits + 7) // 8
            nonce = int.from_bytes(os.urandom(byte_len), "big")

        # Build explicitly so OID matches the chosen hash, not the size guess.
        alg_oid = HASH_OIDS[canonical]
        alg_id = _seq(_oid(alg_oid), _tlv(0x05, b""))
        parts = [
            _integer(1),
            _seq(alg_id, _octet_string(digest)),
        ]
        if req_policy_oid:
            parts.append(_oid(req_policy_oid))
        parts.append(_integer(nonce))
        if cert_req:
            parts.append(_bool(True))
        request_der = _seq(*parts)

        _log("info", "built_from_hash", size=len(request_der), hash=canonical)
        return {
            "request_der": request_der,
            "imprint": digest,
            "imprint_hex": digest.hex(),
            "hash_name": canonical,
            "nonce": nonce,
            "nonce_bits": nonce_bits,
        }

    def _guess_hash_name(digest_len: int) -> str:
        if digest_len == 20:
            return "sha1"
        if digest_len == 32:
            return "sha256"
        if digest_len == 48:
            return "sha384"
        if digest_len == 64:
            return "sha512"
        raise ValueError(
            f"cannot infer hash algorithm from digest length {digest_len}"
        )

    _log("info", "initialized", algorithms=sorted(HASH_OIDS.keys()))

    return {
        "id": "request_builder",
        "version": "1.0.0",
        "priority": 10,
        "description": "RFC3161 TimeStampReq DER builder (pure Python)",
        "hooks": {},
        "build": build,
        "buildFromHash": build_from_hash,
        "supportedHashes": sorted(HASH_OIDS.keys()),
    }