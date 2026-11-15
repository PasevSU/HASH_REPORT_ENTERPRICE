"""Live test: build a TimeStampReq, ask a TSA, parse the response."""
from __future__ import annotations

import hashlib
import os

from loader import load_rfc3161


def der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def der_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + der_len(len(value)) + value


def der_seq(*parts: bytes) -> bytes:
    return der_tlv(0x30, b"".join(parts))


def der_int(v: int) -> bytes:
    raw = v.to_bytes(max(1, (v.bit_length() + 7) // 8), "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return der_tlv(0x02, raw)


def build_request(imprint: bytes, nonce: int) -> bytes:
    sha256_oid = bytes.fromhex("608648016503040201")
    alg_id = der_seq(der_tlv(0x06, sha256_oid), der_tlv(0x05, b""))
    imprint_seq = der_seq(alg_id, der_tlv(0x04, imprint))
    # TimeStampReq ::= SEQUENCE { version, messageImprint, nonce, certReq }
    return der_seq(
        der_int(1),
        imprint_seq,
        der_int(nonce),
        der_tlv(0x01, b"\xff"),
    )


def main() -> int:
    rfc = load_rfc3161({"logger": None})
    parser = rfc["registry"].get("response_parser")

    print("parser version:", parser["version"])
    print("openssl       :", parser["opensslPath"])

    # ---------- Test 3: live request ----------
    imprint = hashlib.sha256(b"loader-test-payload").digest()
    nonce = int.from_bytes(os.urandom(16), "big")
    request_der = build_request(imprint, nonce)

    print("\nTest 3 (live TSA):")
    try:
        import requests
    except ImportError:
        print("  requests not installed — skipping live test")
        return 0

    try:
        r = requests.post(
            "http://timestamp.digicert.com",
            data=request_der,
            headers={
                "Content-Type": "application/timestamp-query",
                "Accept": "application/timestamp-reply",
            },
            timeout=20,
        )
        r.raise_for_status()
    except Exception as exc:
        print("  network error:", type(exc).__name__, exc)
        return 1

    print("  HTTP size :", len(r.content))

    res = parser["parse"](r.content)
    print("  ok         :", res["ok"])
    print("  status     :", res["status"])
    print("  status_str :", res["status_string"])
    print("  gen_time   :", res["gen_time"])
    print("  serial     :", res["serial_number"])
    print("  policy_oid :", res["policy_oid"])
    print("  hash_alg   :", res["hash_algorithm"])
    print("  signer     :", res["signer"])
    print("  sig_alg    :", res["signature_algorithm"])
    print("  imprint    :", res["message_imprint"])
    print("  expected   :", imprint.hex())
    print("  match      :", res["message_imprint"] == imprint.hex())
    print("  nonce      :", res["nonce_int"])
    print("  expected   :", nonce)
    print("  nonce match:", res["nonce_int"] == nonce)
    print("  token_sha  :", (res["token_sha256"] or "")[:32])
    print("  tsr_sha    :", (res["tsr_sha256"] or "")[:32])

    if not res["ok"]:
        print("  errors     :", res["errors"])
        print("  raw_text   :")
        print((res["raw_text"] or "")[:800])
        return 2

    # fail if imprint or nonce mismatch
    if res["message_imprint"] != imprint.hex() or res["nonce_int"] != nonce:
        print("  BINDING MISMATCH")
        return 3

    print("\nPASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())