"""Full round-trip: build TimeStampReq → TSA → parse TimeStampResp."""
from __future__ import annotations

from loader import load_rfc3161


def main() -> int:
    rfc = load_rfc3161({"logger": None})
    builder = rfc["registry"].get("request_builder")
    parser  = rfc["registry"].get("response_parser")

    print("builder version:", builder["version"])
    print("parser  version:", parser["version"])
    print("hashes         :", builder["supportedHashes"])

    # ---- Test 1: build_from_hash with SHA-256 ----
    payload = b"loader-roundtrip-test-payload"
    info = builder["buildFromHash"](payload, hash_name="sha256")
    print("\nTest 1 (build):")
    print("  imprint_hex :", info["imprint_hex"])
    print("  request size:", len(info["request_der"]))
    print("  nonce       :", info["nonce"])
    print("  hash        :", info["hash_name"])

    # ---- Test 2: live request/response ----
    print("\nTest 2 (live TSA):")
    try:
        import requests
    except ImportError:
        print("  requests not installed — skipping")
        return 0

    try:
        r = requests.post(
            "http://timestamp.digicert.com",
            data=info["request_der"],
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

    print("  HTTP size   :", len(r.content))

    res = parser["parse"](r.content)
    print("  status      :", res["status"])
    print("  gen_time    :", res["gen_time"])
    print("  serial      :", res["serial_number"])
    print("  policy_oid  :", res["policy_oid"])

    # ---- Test 3: binding check ----
    imprint_ok = (res["message_imprint"] == info["imprint_hex"])
    nonce_ok   = (res["nonce_int"] == info["nonce"])
    status_ok  = res["ok"]

    print("\nTest 3 (binding):")
    print("  status  ok :", status_ok)
    print("  imprint ok :", imprint_ok)
    print("  nonce   ok :", nonce_ok)

    # ---- Test 4: build_from_hash with SHA-384 ----
    print("\nTest 4 (SHA-384 build):")
    info384 = builder["buildFromHash"](payload, hash_name="sha384")
    print("  imprint_hex :", info384["imprint_hex"])
    print("  size        :", len(info384["request_der"]))
    print("  hash        :", info384["hash_name"])

    # ---- Test 5: build() with precomputed digest ----
    print("\nTest 5 (build from precomputed digest):")
    import hashlib
    digest = hashlib.sha256(payload).digest()
    req = builder["build"](digest)
    print("  size        :", len(req))

    # ---- Test 6: error cases ----
    print("\nTest 6 (error cases):")
    for label, fn in [
        ("empty imprint", lambda: builder["build"](b"")),
        ("unsupported hash", lambda: builder["buildFromHash"](payload, hash_name="md5")),
        ("bad digest size", lambda: builder["build"](b"\x00" * 17)),
    ]:
        try:
            fn()
            print(f"  {label:20}: UNEXPECTED SUCCESS")
        except Exception as exc:
            print(f"  {label:20}: {type(exc).__name__}")

    if status_ok and imprint_ok and nonce_ok:
        print("\nPASS")
        return 0
    print("\nBINDING MISMATCH")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())