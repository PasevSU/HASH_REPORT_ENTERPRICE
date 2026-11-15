"""Fail-closed external RFC3161 PDF verification gate; never stamps or modifies the PDF."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

SCHEMA = "chronoseal.verification-gate/v1"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def qualify(raw: dict, pdf_sha256: str, *, minimum_timestamps: int = 2) -> dict:
    """Strict gate over a separate library-generated audit. No invented verification results."""
    errors = []
    if raw.get("status") != "PASS":
        errors.append("library_status_not_pass")
    if raw.get("input_sha256") != pdf_sha256:
        errors.append("pdf_digest_mismatch")
    stamps = raw.get("timestamps")
    if not isinstance(stamps, list) or len(stamps) < minimum_timestamps:
        errors.append("insufficient_timestamps")
        stamps = []
    for idx, stamp in enumerate(stamps, 1):
        if not isinstance(stamp, dict) or stamp.get("verified") is not True:
            errors.append(f"timestamp_{idx}_not_verified")
        if isinstance(stamp, dict) and stamp.get("verification_error"):
            errors.append(f"timestamp_{idx}_has_error")
    anchors = raw.get("trust_anchors")
    if not isinstance(anchors, list) or not anchors:
        errors.append("missing_trust_anchors")
    return {"schema": SCHEMA, "status": "PASS" if not errors else "BLOCKED", "errors": errors,
            "pdf_sha256": pdf_sha256, "verified_timestamp_count": len(stamps) if not errors else sum(isinstance(s, dict) and s.get("verified") is True for s in stamps),
            "minimum_timestamps": minimum_timestamps, "library_audit": raw}

def verify(pdf: Path, roots: list[Path], output: Path, *, node: str = "node", minimum_timestamps: int = 2) -> dict:
    pdf = pdf.resolve(strict=True)
    if not pdf.is_file() or not roots:
        raise ValueError("PDF file and at least one explicitly approved trust root required")
    roots = [r.resolve(strict=True) for r in roots]
    if any(not r.is_file() for r in roots):
        raise ValueError("Trust root must be a file")
    verifier = Path(__file__).with_name("verify_pdf.mjs")
    initial_hash = sha256_file(pdf)
    with tempfile.TemporaryDirectory(prefix="chronoseal-verify-") as td:
        intermediate = Path(td) / "library_audit.json"
        args = [node, str(verifier), "--input", str(pdf), "--output", str(intermediate)]
        for root in roots:
            args += ["--root", str(root)]
        try:
            completed = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
            raw = json.loads(intermediate.read_text(encoding="utf-8")) if intermediate.exists() else {"status":"ERROR","error":"no library audit"}
            result = qualify(raw, initial_hash, minimum_timestamps=minimum_timestamps)
            if completed.returncode != 0:
                result["errors"].append("verifier_process_failed")
                result["status"] = "BLOCKED"
            result["verifier_exit_code"] = completed.returncode
        except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as exc:
            result = {"schema": SCHEMA, "status": "BLOCKED", "errors": ["verification_execution_failed", type(exc).__name__], "pdf_sha256": initial_hash}
    if sha256_file(pdf) != initial_hash:
        result["errors"].append("pdf_changed_during_verification")
        result["status"] = "BLOCKED"
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".chronoseal-audit-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return result

def main() -> int:
    p = argparse.ArgumentParser(description="Fail-closed PDF RFC3161 verification gate")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True, action="append")
    p.add_argument("--node", default="node")
    p.add_argument("--minimum-timestamps", type=int, choices=[1,2], default=2)
    args = p.parse_args()
    try:
        result = verify(args.input, args.root, args.output, node=args.node, minimum_timestamps=args.minimum_timestamps)
    except Exception as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        return 2
    print(f"{result['status']}: {args.output}")
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
