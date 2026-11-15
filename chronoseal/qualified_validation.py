"""Fail-closed qualified timestamp validation used before final PDF publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chronoseal.trusted_lists import (  # noqa: E402
    verify_lotl_and_member_tsl,
    verify_qualified_tsa_service_status,
)
from hash_report_generator.rfc3161_validation import validate_rfc3161_token  # noqa: E402


def _resolve(root: Path, configured: str | Path) -> Path:
    path = Path(configured).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


# The token validator reads its trust anchors from the process environment, so a
# validation must scope those variables to its own call and restore them after.
_TRUST_ENV = ("CHRONOSEAL_TSA_TRUST_ROOTS", "CHRONOSEAL_TSA_INTERMEDIATES")


def validate_qualified_timestamp(
    *,
    token_der: bytes,
    gen_time: str,
    config: dict[str, Any],
    provider: dict[str, Any],
    project_root: str | Path,
    evidence_dir: str | Path,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    policy = config.get("rfc3161", {})
    list_cfg = policy.get("trusted_list_validation") or {}
    required = ("lotl_file", "lotl_signer_certificate_file", "lotl_signer_sha256", "member_tsl_file", "member_tsl_url")
    missing = [key for key in required if not list_cfg.get(key)]
    if missing:
        raise ValueError("Qualified validation is not provisioned; missing Trusted List fields: " + ", ".join(missing))
    if not provider.get("qualified") or provider.get("trusted_list_service_status") != "granted":
        raise ValueError("STOP provider is not an active qualified service profile")
    if provider.get("service_access_confirmed") is not True:
        raise ValueError(f'{provider.get("name", "Qualified TSA")} service access is not confirmed')
    if provider.get("auth") not in (None, "", "none"):
        raise ValueError(f'Authentication mode "{provider.get("auth")}" is not supported')
    if not provider.get("trust_root_files"):
        raise ValueError("Qualified TSA CA trust anchors are not configured")

    trusted_list_result = verify_lotl_and_member_tsl(
        lotl_path=_resolve(root, list_cfg["lotl_file"]),
        lotl_signer_certificate_path=_resolve(root, list_cfg["lotl_signer_certificate_file"]),
        lotl_signer_sha256=list_cfg["lotl_signer_sha256"],
        member_tsl_path=_resolve(root, list_cfg["member_tsl_file"]),
        member_tsl_url=list_cfg["member_tsl_url"],
    )
    timestamp = datetime.fromisoformat(gen_time.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    service_result = verify_qualified_tsa_service_status(
        _resolve(root, list_cfg["member_tsl_file"]),
        service_name=provider.get("trusted_list_service_name", ""),
        service_certificate_sha256=provider.get("trusted_list_service_certificate_sha256", ""),
        at_time=timestamp,
    )

    roots = [_resolve(root, item) for item in provider.get("trust_root_files", [])]
    intermediates = [
        _resolve(root, item)
        for key in ("intermediate_certificate_files", "embed_certificate_files")
        for item in (provider.get(key, []) or [])
    ]
    service_identity_file = provider.get("trusted_list_service_certificate_file")
    if service_identity_file:
        intermediates.append(_resolve(root, service_identity_file))
    # Never let one provider's anchors leak into the next validation: the token
    # validator reads these variables for the whole process.
    previous_trust_env = {key: os.environ.get(key) for key in _TRUST_ENV}
    os.environ[_TRUST_ENV[0]] = json.dumps([str(path) for path in roots])
    os.environ[_TRUST_ENV[1]] = json.dumps([str(path) for path in intermediates])
    try:
        validation = validate_rfc3161_token(
            token_der=token_der,
            marker="QUALIFIED_STOP",
            openssl_path=config.get("tools", {}).get("openssl"),
            gen_time_text=timestamp.isoformat(),
        )
    finally:
        for key, value in previous_trust_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    expected_service_identity = service_result["identity_sha256"].upper()
    chain_fingerprints = {
        str(item).replace(":", "").upper()
        for item in validation.get("certificate_path_sha256", [])
    }
    if expected_service_identity not in chain_fingerprints:
        raise ValueError(
            "RFC 3161 signer chain does not contain the qualified TSL service identity at genTime"
        )
    if validation.get("chain", {}).get("status") != "GOOD":
        raise ValueError("TSA signer certificate chain did not validate at genTime")
    if validation.get("root_trust_status") != "PASS (explicitly configured trust root)":
        raise ValueError("TSA chain did not terminate at an explicitly configured CA trust anchor")
    revocation = (validation.get("crl", {}), validation.get("ocsp", {}))
    if any(result.get("status") == "REVOKED" for result in revocation):
        raise ValueError("TSA signer is revoked at genTime")
    if not any(result.get("status") == "GOOD" for result in revocation):
        raise ValueError("No authenticated, fresh CRL or OCSP evidence establishes signer status at genTime")
    if any(result.get("status") == "UNKNOWN" for result in revocation):
        raise ValueError("TSA signer revocation evidence contains UNKNOWN status")

    evidence = Path(evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    saved_artifacts = []
    for artifact in validation.get("artifacts", []):
        data = artifact.get("data")
        if not isinstance(data, bytes):
            continue
        filename = Path(str(artifact["filename"])).name
        destination = evidence / filename
        destination.write_bytes(data)
        saved_artifacts.append({
            "filename": filename,
            "kind": artifact.get("kind"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        })
    return {
        "status": "PASS",
        "gen_time": timestamp.isoformat(),
        "trusted_lists": trusted_list_result,
        "service_status": service_result,
        "token_validation": {
            "signer_sha256": validation["signer_sha256"],
            "root_sha256": validation["root_sha256"],
            "root_trust_status": validation["root_trust_status"],
            "chain": validation["chain"],
            "crl": validation["crl"],
            "ocsp": validation["ocsp"],
        },
        "evidence_artifacts": saved_artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--gen-time", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        config_path = Path(args.policy).resolve(strict=True)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        provider = next(
            item for item in config["rfc3161"]["stop"]
            if item.get("name") == args.provider and item.get("qualified") is True
        )
        result = validate_qualified_timestamp(
            token_der=Path(args.token).read_bytes(),
            gen_time=args.gen_time,
            config=config,
            provider=provider,
            project_root=config_path.parent.parent,
            evidence_dir=args.evidence,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"QUALIFIED_TIMESTAMP_VALIDATION_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
