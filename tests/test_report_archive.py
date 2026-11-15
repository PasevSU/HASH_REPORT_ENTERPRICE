import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from chronoseal.report_archive import archive_report, report_id_from_pdf


class ReportArchiveTests(unittest.TestCase):
    def test_numbered_archive_and_sqlite_contain_exact_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "qualified-stop-validation.json").write_text(
                '{"status":"PASS"}\n', encoding="utf-8"
            )
            report = root / "RPT-20261009-072111554-B45A6321_HASHREPORT_TYP_COMBO.pdf"
            report.write_bytes(b"%PDF synthetic final report")
            log = root / "chronoseal.log"
            log.write_text("PASS synthetic run\n", encoding="utf-8")
            manifest = {
                "final_pdf": str(report),
                "final_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                "status": "PASS",
            }

            result = archive_report(
                archive_root=root / "archive",
                database_path=root / "archive" / "reports.sqlite3",
                report_pdf=report,
                evidence_directory=evidence,
                run_log=log,
                manifest=manifest,
            )

            archive = Path(result["archive_directory"])
            self.assertEqual(result["report_id"], "RPT-20261009-072111554-B45A6321")
            self.assertEqual((archive / report.name).read_bytes(), report.read_bytes())
            self.assertEqual((archive / "run.log").read_text(encoding="utf-8"), log.read_text(encoding="utf-8"))
            saved_manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_manifest["archive_database"], result["archive_database"])
            self.assertEqual(saved_manifest["final_pdf"], str(report))

            with closing(sqlite3.connect(result["archive_database"])) as connection:
                record = connection.execute(
                    "SELECT pdf_sha256, manifest_json FROM archive_reports WHERE report_id = ?",
                    (result["report_id"],),
                ).fetchone()
                self.assertEqual(record[0], hashlib.sha256(report.read_bytes()).hexdigest())
                self.assertEqual(json.loads(record[1])["archive_directory"], str(archive))
                rows = connection.execute(
                    "SELECT relative_path, sha256, size_bytes, content FROM archive_files "
                    "WHERE report_id = ? ORDER BY relative_path",
                    (result["report_id"],),
                ).fetchall()
            stored = {path: (digest, size, content) for path, digest, size, content in rows}
            for path in archive.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(archive).as_posix()
                    digest, size, content = stored[relative]
                    self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
                    self.assertEqual(size, len(path.read_bytes()))
                    self.assertEqual(content, path.read_bytes())

    def test_archive_refuses_duplicate_report_number_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            evidence.mkdir()
            report = root / "RPT-1_HASHREPORT_TYP_SINGLE.pdf"
            report.write_bytes(b"%PDF")
            args = {
                "archive_root": root / "archive",
                "database_path": root / "archive" / "reports.sqlite3",
                "report_pdf": report,
                "evidence_directory": evidence,
                "run_log": None,
                "manifest": {"status": "PASS"},
            }
            first = archive_report(**args)
            saved = Path(first["archive_report_pdf"]).read_bytes()
            with self.assertRaises(FileExistsError):
                archive_report(**args)
            self.assertEqual(Path(first["archive_report_pdf"]).read_bytes(), saved)

    def test_database_collision_does_not_publish_or_mutate_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            evidence.mkdir()
            report = root / "RPT-2_HASHREPORT_TYP_SINGLE.pdf"
            report.write_bytes(b"%PDF")
            database = root / "archive" / "reports.sqlite3"
            database.parent.mkdir()
            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    "CREATE TABLE archive_reports (report_id TEXT PRIMARY KEY)"
                )
                connection.execute(
                    "INSERT INTO archive_reports (report_id) VALUES (?)",
                    ("RPT-2",),
                )
                connection.commit()
            manifest = {"status": "PASS"}
            original_manifest = dict(manifest)
            with self.assertRaises(FileExistsError):
                archive_report(
                    archive_root=root / "archive",
                    database_path=database,
                    report_pdf=report,
                    evidence_directory=evidence,
                    run_log=None,
                    manifest=manifest,
                )
            self.assertEqual(manifest, original_manifest)
            self.assertFalse((root / "archive" / "RPT-2").exists())

    def test_manifest_with_path_objects_is_archived_as_text(self):
        # A report built from an explicit file selection used to carry
        # {Path: relative-name} in its manifest. json.dumps() then raised
        # "keys must be str, int, float, bool or None" inside the archive pass,
        # which aborted a run whose report was already signed and finished.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "evidence"
            evidence.mkdir()
            report = root / "RPT-3_HASHREPORT_TYP_COMBO.pdf"
            report.write_bytes(b"%PDF")
            chosen = root / "evidence" / "note.txt"
            chosen.write_text("x", encoding="utf-8")
            manifest = {
                "status": "PASS",
                "selection_paths": {chosen: "note.txt"},
                "selection_files": [chosen],
                "nested": {"deeper": {chosen: {"path": chosen}}},
            }

            result = archive_report(
                archive_root=root / "archive",
                database_path=root / "archive" / "reports.sqlite3",
                report_pdf=report,
                evidence_directory=evidence,
                run_log=None,
                manifest=manifest,
            )

            saved = json.loads(
                (Path(result["archive_directory"]) / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved["selection_paths"], {str(chosen): "note.txt"})
            self.assertEqual(saved["selection_files"], [str(chosen)])
            self.assertEqual(saved["nested"]["deeper"][str(chosen)]["path"], str(chosen))

    def test_report_number_rejects_unsafe_characters(self):
        with self.assertRaises(ValueError):
            report_id_from_pdf("bad name_HASHREPORT_TYP_COMBO.pdf")


if __name__ == "__main__":
    unittest.main()
