"""Helper-enabled subclasses of the original report generators.

Nothing in the original code is modified. Pure inheritance.

Overrides:
    1. _get_tsa_endpoints          -> marker-aware START/STOP selection.
    2. _get_rfc3161_timestamp      -> tracks marker and remembers providers.
    3. _generate_total_checksums   -> bit-length in aggregate labels.
    4. generate                    -> reorganized PDF layout + page identifiers.
"""
from __future__ import annotations

import hashlib
import sys
import zlib
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from loader import load_helpers

from hash_report_single import SingleReportGenerator
from hash_report_combined import CombinedReportGenerator


HELPER_PROVIDERS = [
    {"provider_id": "dfn",        "url": "http://zeitstempel.dfn.de",
     "priority": 10},
    {"provider_id": "digicert",   "url": "http://timestamp.digicert.com",
     "priority": 20},
    {"provider_id": "globalsign", "url": "http://timestamp.globalsign.com/tsa/r45standard",
     "priority": 30},
    {"provider_id": "sectigo",    "url": "http://timestamp.sectigo.com",
     "priority": 40},
]


HASH_BITS = {
    "CRC32":    32,
    "CRC64":    64,
    "SHA1":     160,
    "MD5":      128,
    "SHA256":   256,
    "SHA384":   384,
    "SHA512":   512,
    "SHA3-256": 256,
    "BLAKE2sp": 256,
    "XXH64":    64,
}

HASH_ORDER = [
    "SHA256", "SHA384", "SHA512", "SHA3-256",
    "SHA1", "MD5", "BLAKE2sp",
    "CRC32", "CRC64", "XXH64",
]


class HelperEnabledMixin:
    """Mixin with helper integration and reorganized PDF layout."""

    def __init__(self, logger, include_ots=True):
        super().__init__(logger, include_ots)

        self._helpers = load_helpers({
            "logger": logger,
            "tsaProviders": HELPER_PROVIDERS,
        })
        self._helper_call_log = []
        self._current_marker = None
        self._start_provider_id = None
        self._stop_provider_id = None
        self._bridge_is_single = None
        self._log_helper_summary()

    # ------------------------------------------------------------------
    # override 1: marker-aware TSA endpoint selection
    # ------------------------------------------------------------------
    def _get_tsa_endpoints(self):
        fb = self._helpers["registry"].get("tsa_fallback")
        if fb is None:
            self._record("tsa_fallback", "missing", fallback="original")
            return super()._get_tsa_endpoints()

        marker = (self._current_marker or "START").upper()

        try:
            if marker == "START" or not self._start_provider_id:
                providers = fb["pickForStart"]()
                action = "pickForStart"
            else:
                providers = fb["pickForStop"](self._start_provider_id)
                action = "pickForStop"
        except Exception as exc:
            self._record("tsa_fallback", action="error", error=str(exc),
                         fallback="original")
            return super()._get_tsa_endpoints()

        endpoints = [
            (p["provider_id"].title(), p["url"])
            for p in providers
            if p.get("url")
        ]
        self._record(
            "tsa_fallback", action,
            marker=marker,
            excluded=self._start_provider_id if action == "pickForStop" else None,
            candidates=[p["provider_id"] for p in providers],
        )
        return endpoints

    # ------------------------------------------------------------------
    # override 2: track marker and remember successful START provider
    # ------------------------------------------------------------------
    def _get_rfc3161_timestamp(self, message_imprint=None, force_new=True,
                                marker_label="START"):
        self._current_marker = marker_label
        try:
            result = super()._get_rfc3161_timestamp(
                message_imprint=message_imprint,
                force_new=force_new,
                marker_label=marker_label,
            )
        finally:
            self._current_marker = None

        endpoint = getattr(self, "_last_tsa_endpoint", None)
        if endpoint:
            pid = self._provider_id_for_url(endpoint)
            if marker_label.upper() == "START":
                self._start_provider_id = pid
            elif marker_label.upper() == "END":
                self._stop_provider_id = pid
            self._record(
                "tsa_fallback", "successful_endpoint",
                marker=marker_label.upper(),
                provider=pid,
                url=endpoint,
            )
        return result

    # ------------------------------------------------------------------
    # override 3: bit-length in aggregate labels (COMBINED)
    # ------------------------------------------------------------------
    def _generate_total_checksums(self, files_info):
        base = super()._generate_total_checksums(files_info)
        return {
            f"{algo} ({HASH_BITS.get(algo, '?')} bit)": value
            for algo, value in base.items()
        }

    # ------------------------------------------------------------------
    # override 4: full generate() with reorganized layout + page IDs
    # ------------------------------------------------------------------
    def generate(self, files_info, output_path, *args, **kwargs):
        """Reorganized PDF layout with page-level identifiers."""
        import time as _time
        from pathlib import Path as _Path
        import traceback

        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, Spacer
        from hash_report_generator.a4_document import A4DocTemplate

        from hash_report_core import (
            ReportConstants, FileIcons,
        )
        from bridge.canvas import build_canvas_maker
        from bridge.layout import (
            build_legal_basis,
            build_header_identity,
            build_tsa_issuer_block,
            build_timestamp_total,
            build_embedded_attachments_list,
        )

        try:
            # --- normalize single vs combined signatures ---
            if isinstance(files_info, dict):
                is_single = True
                file_list = [files_info]
                ots_info = args[0] if len(args) > 0 else kwargs.pop("ots_info", None)
                include_explanatory = args[1] if len(args) > 1 else kwargs.pop("include_explanatory", False)
            else:
                is_single = False
                file_list = list(files_info)
                ots_info = kwargs.pop("ots_info", None)
                include_explanatory = args[0] if len(args) > 0 else kwargs.pop("include_explanatory", False)

            _Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            doc = A4DocTemplate(output_path)
            base_styles = getSampleStyleSheet()
            styles = self._create_base_styles(base_styles)
            story = []

            # ---- 1. Title ----
            story.append(Paragraph(
                "SHA-256 Hash Report - Kryptographischer Existenznachweis",
                styles["title_style"],
            ))
            story.append(Spacer(1, ReportConstants.SPACER_HEADING))

            # ---- 2. Legal basis + QR code ----
            build_legal_basis(story, styles)

            # ---- identity + evidence hash ----
            identity = kwargs.pop("report_identity", None)
            if identity is None:
                identity = self._create_report_identity()
            now = identity["now"]
            timezone_str = identity["timezone_str"]
            report_id = identity["report_id"]

            if is_single:
                evidence_sha256 = file_list[0]["hash"]
                report_type = "Individual File Hash Report"
            else:
                # package total checksum = aggregate over all files in the package
                evidence_sha256 = self._generate_checksum(file_list)
                report_type = "Combined File Hash Report (Evidence Package)"

            process_start_ns = _time.perf_counter_ns()

            # ---- START TSA ----
            rfc3161_timestamp_start = self._get_rfc3161_timestamp(
                message_imprint=evidence_sha256, force_new=True,
                marker_label="START",
            )

            # ---- 3. Report ID + Type (centered) ----
            build_header_identity(story, styles, report_id, report_type)

            # ---- 4. START ISSUER block ----
            build_tsa_issuer_block(
                story, styles, "START",
                rfc3161_timestamp_start, self,
            )

            # ---- 5. System info + hashes ----
            self._add_bridge_system_info(
                story, styles, now, timezone_str, report_id,
                files_info=file_list, single_file=is_single,
            )
            story.append(Spacer(1, ReportConstants.SPACER_INFO))

            # ---- 6. Evidence table ----
            if is_single:
                self._add_bridge_single_table(
                    story, styles, file_list[0], report_id,
                )
            else:
                self._add_bridge_combined_table(story, styles, file_list)

            # ---- STOP TSA ----
            end_imprint, start_anchor_type = \
                self._build_end_timestamp_imprint(
                    evidence_sha256, report_id, rfc3161_timestamp_start,
                )
            rfc3161_timestamp_stop = self._get_rfc3161_timestamp(
                message_imprint=end_imprint, force_new=True,
                marker_label="END",
            )
            duration_ms = (_time.perf_counter_ns() - process_start_ns) \
                / 1_000_000.0

            # ---- 7. STOP ISSUER block ----
            build_tsa_issuer_block(
                story, styles, "STOP",
                rfc3161_timestamp_stop, self,
            )

            # ---- 8. TIMESTAMP TOTAL ----
            build_timestamp_total(
                story, styles, self,
                rfc3161_timestamp_start, rfc3161_timestamp_stop,
                evidence_sha256, end_imprint, start_anchor_type,
                duration_ms,
            )

            # ---- 9. Legal + signature ----
            self._add_legal_declaration(
                story, styles, now, timezone_str,
                is_combined=not is_single,
            )
            self._add_footer(
                story, styles, now, timezone_str,
                is_combined=not is_single,
            )

            # ---- 10. Embedded attachments list ----
            attachments = self._collect_pending_attachments()
            build_embedded_attachments_list(story, styles, attachments)

            # ---- build PDF with page-level identifiers ----
            footer_ctx = {
                "report_id":        report_id,
                "package_checksum": evidence_sha256,
                "report_type":      report_type,
                "file_count":       len(file_list),
            }
            canvas_maker = build_canvas_maker(footer_ctx)
            doc.build(story, canvasmaker=canvas_maker)

            # ---- embed actual attachments ----
            try:
                embedded = self._embed_rfc3161_responses_in_pdf(output_path)
            except Exception:
                try:
                    _Path(output_path).unlink(missing_ok=True)
                except Exception:
                    pass
                raise

            for item in embedded:
                print(
                    f"{FileIcons.SUCCESS} Embedded {item['filename']} "
                    f"({self._format_kb(item['size'])}, "
                    f"SHA-256 {item['sha256']})"
                )

            # ---- explanatory (optional) ----
            explanatory_path = None
            if include_explanatory:
                explanatory_path = _Path(output_path).with_name(
                    _Path(output_path).stem + "_-_ERLAEUTERUNG.pdf",
                )
                self._generate_explanatory_pdf(explanatory_path)
                print(
                    f"{FileIcons.SUCCESS} Separate unnumbered explanatory "
                    f"document: {explanatory_path.name}"
                )

            # ---- SQLite ----
            db_result = self._save_sqlite_evidence_database(
                report_id=report_id,
                report_type="INDIVIDUAL" if is_single else "COMBINED",
                generated_at=now,
                timezone_label=timezone_str,
                output_pdf=output_path,
                files_info=file_list,
                evidence_sha256=evidence_sha256,
                start_timestamp_text=rfc3161_timestamp_start,
                end_timestamp_text=rfc3161_timestamp_stop,
                end_message_imprint=end_imprint,
                start_anchor_type=start_anchor_type,
                processing_duration_ms=duration_ms,
                embedded_pdf_artifacts=embedded,
                explanatory_pdf=explanatory_path,
                ots_info=ots_info,
            )
            if db_result:
                print(
                    f"{FileIcons.SUCCESS} SQLite evidence database: "
                    f"{_Path(db_result['path']).name}"
                )
            else:
                print(
                    f"{FileIcons.WARNING} SQLite evidence database could "
                    f"not be updated"
                )

            return True

        except Exception as exc:
            self.logger.error(f"Error generating reorganized PDF: {exc}")
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # helper: system info with hashes right after Hardware ID
    # ------------------------------------------------------------------
    def _add_bridge_system_info(self, story, styles, now, timezone_str,
                                 report_id, files_info, single_file):
        from reportlab.platypus import Paragraph, Spacer
        from hash_report_core import ReportConstants
        from hash_report_generator.pdf_object_rules import block_heading, block_data_style, display_hash
        body_style = block_data_style(styles["normal_style"])

        story.append(block_heading("System Information (Beweissicherung)"))
        story.append(Paragraph(
            f"<b>Generated:</b> {self._format_datetime_ms(now)}", body_style,
        ))
        from chronoseal_volume_report import append_volume_section
        append_volume_section(story, body_style)

        if single_file:
            fi = files_info[0]
            story.append(Paragraph(
                f"<b>File Name:</b> "
                f"{self._sanitize_filename_for_display(fi['name'])}",
                body_style,
            ))
            story.append(Paragraph(
                f"<b>File Size:</b> {self._format_kb(fi['size'])}", body_style,
            ))
            story.append(Paragraph(
                f"<b>SHA-256 Hash:</b> {display_hash(fi['hash'])}", body_style,
            ))
        else:
            story.append(Paragraph(
                f"<b>Total Files:</b> {len(files_info)}", body_style,
            ))
            total_size = sum(f["size"] for f in files_info)
            story.append(Paragraph(
                f"<b>Total Size:</b> {self._format_kb(total_size)}", body_style,
            ))

        story.append(Paragraph(
            f"<b>Hardware ID:</b> "
            f"{self.system_info.get('hardware_id', 'Unknown')}",
            body_style,
        ))
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))

        # ---- Hash block immediately after Hardware ID ----
        if single_file:
            fi = files_info[0]
            try:
                file_hashes = self._compute_all_file_hashes(Path(fi["path"]))
            except Exception:
                file_hashes = {}
            story.append(Paragraph(
                "<b>File Hash Values (all algorithms):</b>", body_style,
            ))
            story.append(Spacer(1, ReportConstants.SPACER_TABLE))
            rows = []
            for algo in HASH_ORDER:
                bits = HASH_BITS.get(algo, "?")
                rows.append((f"{algo} ({bits} bit)", file_hashes.get(algo, "")))
            self._add_aligned_key_value_table(
                story, rows, styles, label_ratio=0.25, compact=True,
            )
        else:
            checksums = self._generate_total_checksums(files_info)
            story.append(Paragraph(
                "<b>Package Total Checksum (sum of all files):</b>",
                body_style,
            ))
            story.append(Spacer(1, ReportConstants.SPACER_TABLE))
            self._add_aligned_key_value_table(
                story, list(checksums.items()), styles,
                label_ratio=0.25, compact=True,
            )
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))

        # ---- remaining system info after hashes ----
        story.append(Paragraph(
            f"<b>Computer Name:</b> "
            f"{self.system_info.get('computer_name', 'Unknown')}",
            body_style,
        ))
        story.append(Paragraph(
            f"<b>Operating System:</b> "
            f"{self.system_info.get('os', 'Unknown')} "
            f"{self.system_info.get('os_version', '')}",
            body_style,
        ))
        story.append(Paragraph(
            f"<b>Generated by:</b> "
            f"{self.user_info.get('username', 'Unknown')}",
            body_style,
        ))

    # ------------------------------------------------------------------
    # helper: single file info table
    # ------------------------------------------------------------------
    def _add_bridge_single_table(self, story, styles, file_info, report_id):
        from hash_report_generator.pdf_object_rules import display_hash
        from reportlab.platypus import Paragraph, Spacer, Table
        from hash_report_core import ReportConstants

        story.append(Paragraph(
            "<b>File Information:</b>", styles["normal_style"],
        ))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))

        data = [[
            Paragraph("<b>Property</b>", styles["header_style"]),
            Paragraph("<b>Value</b>", styles["header_style"]),
        ]]
        rows = [
            ("File Name",
             self._sanitize_filename_for_display(file_info["name"])),
            ("File Size", self._format_kb(file_info["size"])),
            ("Created",
             self._format_datetime_plain_ms(file_info["created"])),
            ("Last Modified",
             self._format_datetime_plain_ms(file_info["modified"])),
            ("SHA-256 Hash", display_hash(file_info["hash"])),
            ("Hardware ID", self.system_info.get("hardware_id", "Unknown")),
            ("Report ID", report_id),
        ]
        for k, v in rows:
            data.append([
                Paragraph(k, styles["table_text_style"]),
                Paragraph(v, styles["table_text_style"]),
            ])

        table = Table(
            data, repeatRows=1,
            colWidths=self._calculate_column_widths(
                ReportConstants.INFO_TABLE_COL_PROPORTIONS,
            ),
        )
        self._apply_table_style(table, table_type="standard")
        story.append(table)
        story.append(Spacer(1, ReportConstants.SPACER_AFTER_TABLE))

    # ------------------------------------------------------------------
    # helper: combined evidence table
    # ------------------------------------------------------------------
    def _add_bridge_combined_table(self, story, styles, files_info):
        from reportlab.platypus import Paragraph, Spacer, Table
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from hash_report_core import ReportConstants

        story.append(Paragraph(
            "<b>Evidence Package Files Information:</b>",
            styles["normal_style"],
        ))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))

        safe_style = ParagraphStyle(
            "BridgeSafeStyle",
            parent=styles["table_text_style"],
            wordWrap="WORD",
            fontSize=ReportConstants.FONT_SIZE_TABLE_TEXT,
            leading=ReportConstants.LEADING_TABLE_TEXT,
            alignment=TA_LEFT,
        )
        hash_style = ParagraphStyle(
            "BridgeHashStyle",
            parent=styles["hash_style"],
            wordWrap="WORD",
            fontSize=ReportConstants.FONT_SIZE_TABLE_HASH,
            leading=ReportConstants.LEADING_TABLE_HASH,
            alignment=TA_LEFT,
        )
        header_style = ParagraphStyle(
            "BridgeHeaderStyle",
            parent=styles["header_style"],
            alignment=TA_CENTER,
            fontSize=ReportConstants.FONT_SIZE_TABLE_HEADER,
        )

        from combined_table_layout import index_cell, size_kb_cell, digest_cell
        data = [[
            Paragraph("<b>#</b>", header_style),
            Paragraph("<b>File Name</b>", header_style),
            Paragraph("<b>Type</b>", header_style),
            Paragraph("<b>Size (KB)</b>", header_style),
            Paragraph("<b>Created</b>", header_style),
            Paragraph("<b>Modified</b>", header_style),
            Paragraph("<b>SHA-256 Hash</b>", header_style),
        ]]
        sorted_files = sorted(
            files_info,
            key=lambda x: (self._get_type_priority(x["type"]), x["name"]),
        )
        for idx, fi in enumerate(sorted_files, 1):
            data.append([
                index_cell(idx, safe_style),
                Paragraph(
                    self._sanitize_filename_for_display(fi["name"]),
                    safe_style,
                ),
                Paragraph(fi["type"], safe_style),
                Paragraph(size_kb_cell(self._format_kb(fi["size"])), safe_style),
                Paragraph(
                    self._format_datetime_plain_ms(fi["created"]),
                    safe_style,
                ),
                Paragraph(
                    self._format_datetime_plain_ms(fi["modified"]),
                    safe_style,
                ),
                digest_cell(fi["hash"], hash_style),
            ])

        props = ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7
        col_widths = [
            self.table_width * props["number"],
            self.table_width * props["name"],
            self.table_width * props["type"],
            self.table_width * props["size"],
            self.table_width * props["created"],
            self.table_width * props["modified"],
            self.table_width * props["hash"],
        ]
        table = Table(data, repeatRows=1, colWidths=col_widths)
        from hash_report_generator.pdf_object_rules import globalize_table
        globalize_table(table, alignments='combined')
        story.append(table)
        story.append(Spacer(1, ReportConstants.SPACER_AFTER_TABLE))

    # ------------------------------------------------------------------
    # helper: list of attachments that will be embedded
    # ------------------------------------------------------------------
    def _collect_pending_attachments(self):
        responses = getattr(self, "_rfc3161_responses", {}) or {}
        artifacts_map = getattr(
            self, "_rfc3161_validation_artifacts", {},
        ) or {}

        items = []
        for marker in ("START", "END"):
            display_marker = "STOP" if marker == "END" else marker
            data = responses.get(marker)
            if data:
                raw = bytes(data)
                items.append({
                    "filename": f"RFC3161_{display_marker}.tsr",
                    "marker": display_marker,
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
            for artifact in artifacts_map.get(marker, []) or []:
                art_data = artifact.get("data")
                art_name = artifact.get("filename")
                if not art_data or not art_name:
                    continue
                external_name = str(art_name)
                if marker == "END" and \
                        external_name.startswith("RFC3161_END_"):
                    external_name = "RFC3161_STOP_" + \
                        external_name[len("RFC3161_END_"):]
                raw = bytes(art_data)
                items.append({
                    "filename": external_name,
                    "marker": display_marker,
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
        return items

    # ------------------------------------------------------------------
    # helper: compute all 10 hashes on the file bytes directly
    # ------------------------------------------------------------------
    def _compute_all_file_hashes(self, file_path):
        file_path = Path(file_path)
        data = file_path.read_bytes()
        return {
            "SHA256":   hashlib.sha256(data).hexdigest(),
            "SHA384":   hashlib.sha384(data).hexdigest(),
            "SHA512":   hashlib.sha512(data).hexdigest(),
            "SHA3-256": hashlib.sha3_256(data).hexdigest(),
            "SHA1":     hashlib.sha1(data).hexdigest(),
            "MD5":      hashlib.md5(data, usedforsecurity=False).hexdigest(),
            "BLAKE2sp": self._blake2sp(data),
            "CRC32":    f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
            "CRC64":    f"{self._crc64_xz(data):016x}",
            "XXH64":    f"{self._xxh64(data):016x}",
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _provider_id_for_url(self, url):
        if not url:
            return None
        clean = url.rstrip("/").lower()
        for p in HELPER_PROVIDERS:
            if p["url"].rstrip("/").lower() == clean:
                return p["provider_id"]
        return None

    def _record(self, module_id, method, **extra):
        entry = {"module": module_id, "method": method, **extra}
        self._helper_call_log.append(entry)
        if self.logger:
            self.logger.info(f"[bridge] {module_id}.{method} {extra}")

    def _log_helper_summary(self):
        summary = self._helpers.get("summary") or {}
        if self.logger:
            self.logger.info(
                f"[bridge] loaded helpers: "
                f"modules={summary.get('modules')} "
                f"errors={summary.get('errors')}"
            )

    def helper_call_log(self):
        return list(self._helper_call_log)

    def helper_registry(self):
        return self._helpers["registry"]

    def bridge_provider_summary(self):
        return {
            "start_provider": self._start_provider_id,
            "stop_provider": self._stop_provider_id,
            "independent": bool(
                self._start_provider_id and
                self._stop_provider_id and
                self._start_provider_id != self._stop_provider_id
            ),
        }


class HelperEnabledSingleReportGenerator(HelperEnabledMixin, SingleReportGenerator):
    """Single report with reorganized layout + page identifiers."""
    pass


class HelperEnabledCombinedReportGenerator(HelperEnabledMixin, CombinedReportGenerator):
    """Combined report with reorganized layout + page identifiers."""
    pass
