"""SQLite persistence for hash-report metadata and binary evidence artifacts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_FILENAME = "hash_report_evidence.sqlite3"
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    timezone_label TEXT NOT NULL,
    output_pdf TEXT NOT NULL,
    output_sha256 TEXT NOT NULL,
    output_size INTEGER NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT NOT NULL,
    end_message_imprint TEXT NOT NULL,
    start_anchor_type TEXT NOT NULL,
    processing_duration_ms REAL NOT NULL,
    explanatory_pdf TEXT,
    explanatory_pdf_sha256 TEXT,
    system_info_json TEXT NOT NULL,
    user_info_json TEXT NOT NULL,
    ots_info_json TEXT,
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS report_files (
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    size_bytes INTEGER,
    sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (report_id, ordinal)
);
CREATE TABLE IF NOT EXISTS report_artifacts (
    report_id TEXT NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,
    marker TEXT,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    data BLOB NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (report_id, ordinal),
    UNIQUE (report_id, filename)
);
CREATE INDEX IF NOT EXISTS idx_report_files_sha256 ON report_files(sha256);
CREATE INDEX IF NOT EXISTS idx_report_artifacts_sha256 ON report_artifacts(sha256);
"""


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"encoding": "base64", "data": __import__("base64").b64encode(value).decode("ascii")}
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_artifact_bytes(item: dict[str, Any]) -> bytes | None:
    data = item.get("data")
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    path_value = item.get("path")
    if path_value:
        path = Path(path_value)
        if path.is_file():
            return path.read_bytes()
    return None


def build_record(
    generator: Any,
    *,
    report_id: str,
    report_type: str,
    generated_at: datetime,
    timezone_label: str,
    output_pdf: Path,
    files_info: list[dict[str, Any]],
    evidence_sha256: str,
    start_timestamp_text: str,
    end_timestamp_text: str,
    end_message_imprint: str,
    start_anchor_type: str,
    processing_duration_ms: float,
    embedded_pdf_artifacts: list[dict[str, Any]],
    explanatory_pdf: Path | None = None,
    ots_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate the complete normalized record before opening SQLite."""
    if not report_id or not report_type:
        raise ValueError("report_id and report_type are required")
    output_pdf = Path(output_pdf).expanduser().resolve(strict=True)
    if not output_pdf.is_file():
        raise ValueError(f"Report PDF is not a file: {output_pdf}")
    report_hash = _sha256(output_pdf)
    explanatory_pdf = Path(explanatory_pdf).expanduser().resolve(strict=True) if explanatory_pdf else None
    if explanatory_pdf and not explanatory_pdf.is_file():
        raise ValueError(f"Explanatory PDF is not a file: {explanatory_pdf}")

    normalized_files = []
    for ordinal, item in enumerate(files_info, 1):
        if not isinstance(item, dict):
            raise TypeError(f"files_info[{ordinal - 1}] must be a mapping")
        digest = str(item.get("hash") or item.get("sha256") or "").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"files_info[{ordinal - 1}] has no valid SHA-256")
        path = str(item.get("path") or "")
        name = str(item.get("name") or Path(path).name)
        if not name:
            raise ValueError(f"files_info[{ordinal - 1}] has no filename")
        size = item.get("size_bytes", item.get("size"))
        normalized_files.append({
            "ordinal": ordinal,
            "path": path,
            "name": name,
            "size_bytes": int(size) if size is not None else None,
            "sha256": digest,
            "metadata_json": _json(item),
        })

    artifacts = []
    known_names: set[str] = set()
    sources = [*(embedded_pdf_artifacts or [])]
    for marker, values in (getattr(generator, "_rfc3161_validation_artifacts", {}) or {}).items():
        for value in values or []:
            sources.append({**value, "marker": value.get("marker") or marker})
    seen_artifacts: dict[str, bytes] = {}
    for ordinal, item in enumerate(sources, 1):
        if not isinstance(item, dict):
            raise TypeError(f"artifact[{ordinal - 1}] must be a mapping")
        filename = str(item.get("filename") or "").strip()
        data = _read_artifact_bytes(item)
        if not filename or data is None:
            continue
        if filename in known_names:
            if seen_artifacts.get(filename) != data:
                raise ValueError(f"Duplicate evidence artifact filename: {filename}")
            continue  # byte-identical artifact shared by START and STOP is stored once
        known_names.add(filename)
        seen_artifacts[filename] = data
        digest = hashlib.sha256(data).hexdigest()
        declared = str(item.get("sha256") or "").lower()
        if declared and declared != digest:
            raise ValueError(f"Artifact SHA-256 mismatch: {filename}")
        artifacts.append({
            "ordinal": len(artifacts) + 1,
            "filename": filename,
            "kind": str(item.get("kind") or "EVIDENCE_ARTIFACT"),
            "marker": item.get("marker"),
            "sha256": digest,
            "size_bytes": len(data),
            "data": data,
            "metadata_json": _json({k: v for k, v in item.items() if k != "data"}),
        })

    for marker, encoded in (getattr(generator, "_rfc3161_responses", {}) or {}).items():
        if not encoded:
            continue
        filename = f"RFC3161_{'STOP' if marker == 'END' else marker}.tsr"
        if filename not in known_names:
            data = bytes(encoded)
            artifacts.append({
                "ordinal": len(artifacts) + 1,
                "filename": filename,
                "kind": "RFC3161_TIMESTAMP_RESPONSE",
                "marker": marker,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "data": data,
                "metadata_json": "{}",
            })

    return {
        "report_id": str(report_id),
        "report_type": str(report_type),
        "generated_at": generated_at.isoformat(),
        "timezone_label": str(timezone_label),
        "output_pdf": str(output_pdf),
        "output_sha256": report_hash,
        "output_size": output_pdf.stat().st_size,
        "evidence_sha256": str(evidence_sha256).lower(),
        "start_timestamp": str(start_timestamp_text or ""),
        "end_timestamp": str(end_timestamp_text or ""),
        "end_message_imprint": str(end_message_imprint or ""),
        "start_anchor_type": str(start_anchor_type or ""),
        "processing_duration_ms": float(processing_duration_ms),
        "explanatory_pdf": str(explanatory_pdf) if explanatory_pdf else None,
        "explanatory_pdf_sha256": _sha256(explanatory_pdf) if explanatory_pdf else None,
        "system_info_json": _json(getattr(generator, "system_info", {}) or {}),
        "user_info_json": _json(getattr(generator, "user_info", {}) or {}),
        "ots_info_json": _json(ots_info) if ots_info is not None else None,
        "files": normalized_files,
        "artifacts": artifacts,
    }


def save_record(database_path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Atomically insert or replace one report and its complete evidence rows."""
    database_path = Path(database_path).expanduser().resolve()
    if database_path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
        raise ValueError("Evidence database path must use .sqlite, .sqlite3 or .db")
    if Path(record["output_pdf"]).resolve() == database_path:
        raise ValueError("Evidence database cannot overwrite the report PDF")
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(database_path), timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.executescript(_SCHEMA)
        with connection:
            versions = connection.execute("SELECT version FROM schema_info").fetchall()
            if versions and max(row[0] for row in versions) > SCHEMA_VERSION:
                raise RuntimeError("Evidence database was created by a newer ChronoSeal version")
            connection.execute("DELETE FROM schema_info")
            connection.execute("INSERT INTO schema_info(version) VALUES (?)", (SCHEMA_VERSION,))
            connection.execute("DELETE FROM reports WHERE report_id = ?", (record["report_id"],))
            connection.execute(
                """INSERT INTO reports (
                    report_id, report_type, generated_at, timezone_label, output_pdf,
                    output_sha256, output_size, evidence_sha256, start_timestamp,
                    end_timestamp, end_message_imprint, start_anchor_type,
                    processing_duration_ms, explanatory_pdf, explanatory_pdf_sha256,
                    system_info_json, user_info_json, ots_info_json
                ) VALUES (
                    :report_id, :report_type, :generated_at, :timezone_label, :output_pdf,
                    :output_sha256, :output_size, :evidence_sha256, :start_timestamp,
                    :end_timestamp, :end_message_imprint, :start_anchor_type,
                    :processing_duration_ms, :explanatory_pdf, :explanatory_pdf_sha256,
                    :system_info_json, :user_info_json, :ots_info_json
                )""",
                record,
            )
            connection.executemany(
                """INSERT INTO report_files
                    (report_id, ordinal, path, name, size_bytes, sha256, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (record["report_id"], item["ordinal"], item["path"], item["name"],
                     item["size_bytes"], item["sha256"], item["metadata_json"])
                    for item in record["files"]
                ],
            )
            connection.executemany(
                """INSERT INTO report_artifacts
                    (report_id, ordinal, filename, kind, marker, sha256, size_bytes, data, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (record["report_id"], item["ordinal"], item["filename"], item["kind"],
                     item["marker"], item["sha256"], item["size_bytes"], sqlite3.Binary(item["data"]),
                     item["metadata_json"])
                    for item in record["artifacts"]
                ],
            )
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()

    digest = _sha256(database_path)
    return {
        "path": str(database_path),
        "sha256": digest,
        "report_id": record["report_id"],
        "file_count": len(record["files"]),
        "artifact_count": len(record["artifacts"]),
    }
