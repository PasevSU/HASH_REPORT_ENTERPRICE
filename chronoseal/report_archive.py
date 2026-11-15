"""Durable report archive: numbered folders plus a SQLite copy of every artifact."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .util import json_safe


_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_reports (
    report_id TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    report_path TEXT NOT NULL,
    archive_directory TEXT NOT NULL,
    database_path TEXT NOT NULL,
    pdf_sha256 TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS archive_files (
    report_id TEXT NOT NULL REFERENCES archive_reports(report_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content BLOB NOT NULL,
    PRIMARY KEY (report_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_archive_files_sha256 ON archive_files(sha256);
"""


def report_id_from_pdf(path: str | Path) -> str:
    stem = Path(path).stem
    report_id = stem.split("_HASHREPORT_TYP_", 1)[0]
    if not report_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", report_id):
        raise ValueError(f"Cannot derive a safe report number from PDF name: {Path(path).name}")
    return report_id


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_WINDOWS_TRANSIENT_WINERRORS = (5, 32, 33)


def _rename_with_retry(source: Path, destination: Path, attempts: int = 6) -> None:
    """Publish the staged folder, retrying a transient Windows sharing violation.

    Antivirus and the search indexer briefly open files inside a folder that was
    just written, so ``os.rename`` can fail with WinError 5/32/33 on a directory
    that is not actually in use. One failed publish would leave the report number
    blocked by the destination guard, so the rename is retried with backoff.
    """
    delay = 0.05
    for attempt in range(1, attempts + 1):
        try:
            os.rename(source, destination)
            return
        except OSError as error:
            transient = (
                os.name == "nt"
                and getattr(error, "winerror", None) in _WINDOWS_TRANSIENT_WINERRORS
            )
            if not transient or attempt == attempts:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.8)

def archive_report(
    *,
    archive_root: str | Path,
    database_path: str | Path,
    report_pdf: str | Path,
    evidence_directory: str | Path,
    run_log: str | Path | None,
    manifest: dict[str, Any],
    report_name: str | None = None,
) -> dict[str, str]:
    """Publish one immutable report bundle and index all its files in SQLite.

    report_name is the published report file name (carries the report number);
    the source PDF may have an internal name such as sealed-verified.pdf.
    """
    pdf = Path(report_pdf).expanduser().resolve(strict=True)
    evidence = Path(evidence_directory).expanduser().resolve(strict=True)
    if not pdf.is_file() or not evidence.is_dir():
        raise ValueError("Archive requires a report PDF and its evidence directory")
    log = Path(run_log).expanduser().resolve(strict=True) if run_log else None
    if log is not None and not log.is_file():
        raise ValueError(f"Run log is not a file: {log}")

    root = Path(archive_root).expanduser().resolve()
    database = Path(database_path).expanduser().resolve()
    archive_name = Path(report_name).name if report_name else pdf.name
    report_id = report_id_from_pdf(archive_name)
    destination = root / report_id
    if database == destination or destination in database.parents:
        raise ValueError("Archive database must be outside each numbered report folder")
    root.mkdir(parents=True, exist_ok=True)
    database.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Report archive already exists; refusing overwrite: {destination}")

    stage = root / f".{report_id}.{uuid.uuid4().hex}.partial"
    published = False
    connection: sqlite3.Connection | None = None
    try:
        stage.mkdir()
        shutil.copy2(pdf, stage / archive_name)
        shutil.copytree(evidence, stage / "evidence")
        if log:
            shutil.copy2(log, stage / "run.log")
        else:
            (stage / "run.log").write_text(
                "Session log unavailable; see evidence artifacts and manifest.\n",
                encoding="utf-8",
            )

        archive_manifest = json_safe({
            **manifest,
            "report_id": report_id,
            "archive_directory": str(destination),
            "archive_report_pdf": str(destination / archive_name),
            "archive_manifest": str(destination / "manifest.json"),
            "archive_log": str(destination / "run.log"),
            "archive_evidence_directory": str(destination / "evidence"),
            "archive_database": str(database),
        })
        (stage / "evidence" / "manifest.json").write_text(
            json.dumps(archive_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (stage / "manifest.json").write_text(
            json.dumps(archive_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        connection = sqlite3.connect(str(database), timeout=30)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.executescript(_SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM archive_reports WHERE report_id = ?", (report_id,)
        ).fetchone():
            raise FileExistsError(f"Report number already exists in archive database: {report_id}")

        manifest_json = json.dumps(archive_manifest, ensure_ascii=False, sort_keys=True)
        connection.execute(
            """INSERT INTO archive_reports (
                   report_id, created_utc, report_path, archive_directory,
                   database_path, pdf_sha256, manifest_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                datetime.now(timezone.utc).isoformat(),
                str(destination / archive_name),
                str(destination),
                str(database),
                _sha256(stage / archive_name),
                manifest_json,
            ),
        )
        for item in sorted(path for path in stage.rglob("*") if path.is_file()):
            relative = item.relative_to(stage).as_posix()
            data = item.read_bytes()
            connection.execute(
                """INSERT INTO archive_files (
                       report_id, relative_path, sha256, size_bytes, content
                   ) VALUES (?, ?, ?, ?, ?)""",
                (report_id, relative, hashlib.sha256(data).hexdigest(), len(data), data),
            )

        if destination.exists():
            raise FileExistsError(f"Report archive already exists; refusing overwrite: {destination}")
        _rename_with_retry(stage, destination)
        published = True
        connection.commit()
        manifest.clear()
        manifest.update(archive_manifest)
        return {
            "report_id": report_id,
            "archive_directory": str(destination),
            "archive_report_pdf": str(destination / archive_name),
            "archive_manifest": str(destination / "manifest.json"),
            "archive_log": str(destination / "run.log"),
            "archive_database": str(database),
        }
    except BaseException:
        # BaseException keeps Ctrl+C inside the same atomicity guarantee: the
        # folder must never survive without its committed database row, because
        # the report number would then be blocked by the destination guard.
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
        if published and destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        if connection is not None:
            connection.close()
        if stage.exists():
            # Cleanup must never mask the primary failure with a secondary one.
            shutil.rmtree(stage, ignore_errors=True)
