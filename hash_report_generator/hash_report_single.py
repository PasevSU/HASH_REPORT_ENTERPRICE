#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SHA-256 HASH REPORT GENERATOR v2.34 - SINGLE REPORT
═══════════════════════════════════════════════════════════════════════════════

Генерира индивидуален SHA-256 хеш отчет за единичен файл.
Използва споделеното ядро от hash_report_core.py.

ФИКС v2.34:
  - START/END TimeStampResp (.tsr) са binary embedded attachments в PDF; Base64 страниците са премахнати
  - Total Checksum е изведен като RFC3161-style bullet block без таблица
  - Пълна Unicode поддръжка за timestamp секцията с автоматично откриване на шрифтове
  - Премахнато съкращаване на всички полета (Nonce, Hash, Data, Signature)
  - Уникален RFC 3161 timestamp за всеки отчет
  - RFC 3161 START/END с primary + 3 резервни TSA endpoints
  - Всички размери в PDF са само в KB; всички локални времена са до милисекунда
  - Име на PDF: YYYY-MM-DD-HHMMSSmmm_-_REPORTID-HASHREPORT.pdf; без презаписване
"""

import sys
from pathlib import Path
import logging
import traceback
import time

_report_dir = Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if _report_path not in sys.path:
        sys.path.insert(0, _report_path)

# Импорт на споделеното ядро
from hash_report_core import (
    HashGeneratorCore,
    ReportConstants,
    ConsoleColors,
    FileIcons,
    NumberedCanvas,
    UNICODE_FONT_NAME,
    UNICODE_FONT_AVAILABLE,
    REPORTLAB_AVAILABLE,
    install_requirements
)

# Допълнителни импорти за PDF
from reportlab.platypus import Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from hash_report_generator.a4_document import A4DocTemplate
from hash_report_generator.pdf_object_rules import display_hash


class SingleReportGenerator(HashGeneratorCore):
    """
    Генератор на индивидуални SHA-256 хеш отчети.
    Наследява общата функционалност от HashGeneratorCore.
    """

    def __init__(self, logger, include_ots=True):
        """
        Инициализира генератора за индивидуални отчети.

        Args:
            logger: Logger инстанция
            include_ots: Дали да включва OTS информация
        """
        super().__init__(logger, include_ots)

    # ========================================================================
    # МЕТОДИ ЗА ФАЙЛОВА ИНФОРМАЦИЯ
    # ========================================================================
    def get_file_info(self, file_path: Path) -> dict:
        """Взема информация за файл"""
        try:
            stat = file_path.stat()
            created, modified = self._get_file_times(file_path)
            file_hash = self.calculate_sha256(file_path)
            final_stat = file_path.stat()
            if (stat.st_size, stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
                raise RuntimeError(f"File changed while collecting metadata: {file_path}")
            return {
                "name": file_path.name,
                "path": str(file_path),
                "size": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 2),
                "created": created,
                "modified": modified,
                "hash": file_hash
            }
        except Exception as e:
            self.logger.error(f"Error reading file {file_path}: {e}")
            return None

    def _get_report_name(self, file_info: dict, report_type: str,
                         report_identity: dict = None) -> str:
        """Return the unique Windows-safe report filename.

        file_info/report_type are retained for API compatibility; report identity,
        not the source filename, controls the output name.
        """
        identity = report_identity or self._create_report_identity()
        return f"{identity['report_id']}_HASHREPORT_TYP_SINGLE.pdf"

    # ========================================================================
    # ГЕНЕРИРАНЕ НА ИНДИВИДУАЛЕН ОТЧЕТ
    # ========================================================================
    def generate(self, file_info: dict, output_path: str,
                 ots_info: dict = None,
                 include_explanatory: bool = False,
                 report_identity: dict = None) -> bool:
        """
        Генерира индивидуален отчет за един файл с уникален timestamp.

        Args:
            file_info: Информация за файла
            output_path: Път за запазване на PDF
            ots_info: OTS информация (опционално)
            include_explanatory: Дали да включи пояснителен документ

        Returns:
            bool: True при успех, False при грешка
        """
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            doc = A4DocTemplate(output_path)

            base_styles = getSampleStyleSheet()
            styles = self._create_base_styles(base_styles)
            from hash_report_generator.report_header import apply_header_palette, build_report_header
            apply_header_palette(styles)
            story = build_report_header(doc.width, styles, {
                'section': ReportConstants.SPACER_SECTION,
                'title': ReportConstants.SPACER_TITLE,
                'legal': ReportConstants.SPACER_LEGAL,
            })

            identity = report_identity or self._create_report_identity()
            now = identity['now']
            timezone_str = identity['timezone_str']
            report_id = identity['report_id']

            # START RFC 3161 over the original file SHA-256.
            evidence_sha256 = file_info['hash']
            process_start_ns = time.perf_counter_ns()
            rfc3161_timestamp = self._get_rfc3161_timestamp(
                message_imprint=evidence_sha256, force_new=True, marker_label='START')

            # Системна информация
            self._add_system_info_section(story, styles, now, timezone_str, report_id,
                                          files_info=[file_info], single_file=True,
                                          rfc3161_timestamp=rfc3161_timestamp)
            story.append(Spacer(1, ReportConstants.SPACER_INFO))

            # Таблица с информация за файла
            story.append(Paragraph("<b>File Information:</b>", styles['normal_style']))
            story.append(Spacer(1, ReportConstants.SPACER_TABLE))

            table_data = [[
                Paragraph("<b>Property</b>", styles['header_style']),
                Paragraph("<b>Value</b>", styles['header_style'])
            ]]

            rows = [
                ["File Name", self._sanitize_filename_for_display(file_info['name'])],
                ["File Size", self._format_kb(file_info['size'])],
                ["Created", self._format_datetime_plain_ms(file_info['created'])],
                ["Last Modified", self._format_datetime_plain_ms(file_info['modified'])],
                ["SHA-256 Hash", display_hash(file_info['hash'])],
                ["Hardware ID", self.system_info.get('hardware_id', 'Unknown')],
                ["Report ID", report_id],
            ]

            for row in rows:
                table_data.append([
                    Paragraph(row[0], styles['table_text_style']),
                    Paragraph(row[1], styles['table_text_style'])
                ])

            table = Table(table_data, repeatRows=1,
                colWidths=self._calculate_column_widths(ReportConstants.INFO_TABLE_COL_PROPORTIONS))
            self._apply_table_style(table, table_type='standard')
            story.append(table)
            story.append(Spacer(1, ReportConstants.SPACER_AFTER_TABLE))

            # END RFC 3161 closes the actual individual report.
            # Explanatory material is generated as a separate PDF.
            # END RFC 3161 closes this individual report-generation interval.
            end_imprint, start_anchor_type = self._build_end_timestamp_imprint(
                evidence_sha256, report_id, rfc3161_timestamp)
            end_timestamp = self._get_rfc3161_timestamp(
                message_imprint=end_imprint, force_new=True, marker_label='END')
            duration_ms = (time.perf_counter_ns() - process_start_ns) / 1_000_000.0

            self._add_end_timestamp_section(
                story, styles, end_timestamp, duration_ms, evidence_sha256,
                end_imprint, start_anchor_type)
            # v2.35: final declaration belongs at the physical end of the visible report,
            # after the STOP timestamp section.
            self._add_legal_declaration(story, styles, now, timezone_str, is_combined=False)
            self._add_footer(story, styles, now, timezone_str, is_combined=False)
            # v2.34: keep pages compact; embed the original TSA responses instead
            # of printing complete Base64 tokens in the visible report.
            doc.build(story, canvasmaker=NumberedCanvas)
            try:
                embedded_rfc3161 = self._embed_rfc3161_responses_in_pdf(output_path)
            except Exception:
                # Never leave a PDF that claims embedded RFC3161 evidence when
                # the attachment step did not complete successfully.
                try:
                    Path(output_path).unlink(missing_ok=True)
                except Exception:
                    pass
                raise
            for item in embedded_rfc3161:
                print(f"{FileIcons.SUCCESS} Embedded {item['filename']} ({self._format_kb(item['size'])}, SHA-256 {item['sha256']})")
            explanatory_path = None
            if include_explanatory and __import__('os').environ.get('CHRONOSEAL_INCLUDE_EXPLANATION', '1') != '0':
                explanatory_path = Path(output_path).with_name(Path(output_path).stem + '_-_ERLAEUTERUNG.pdf')
                self._generate_explanatory_pdf(explanatory_path)
                print(f"{FileIcons.SUCCESS} Separate unnumbered explanatory document: {explanatory_path.name}")

            db_result = self._save_sqlite_evidence_database(
                report_id=report_id, report_type='INDIVIDUAL', generated_at=now,
                timezone_label=timezone_str, output_pdf=output_path, files_info=[file_info],
                evidence_sha256=evidence_sha256, start_timestamp_text=rfc3161_timestamp,
                end_timestamp_text=end_timestamp, end_message_imprint=end_imprint,
                start_anchor_type=start_anchor_type, processing_duration_ms=duration_ms,
                embedded_pdf_artifacts=embedded_rfc3161, explanatory_pdf=explanatory_path,
                ots_info=ots_info,
            )
            if db_result:
                print(f"{FileIcons.SUCCESS} SQLite evidence database: {Path(db_result['path']).name}")
                print(f"  SHA-256: {db_result['sha256']}")
            else:
                print(f"{FileIcons.WARNING} SQLite evidence database could not be updated")
            return True

        except Exception as e:
            self.logger.error(f"Error generating PDF for {file_info['name']}: {e}")
            traceback.print_exc()
            return False


# ============================================================================
# САМОСТОЯТЕЛНО ИЗПЪЛНЕНИЕ - ИНДИВИДУАЛЕН ОТЧЕТ
# ============================================================================
if __name__ == "__main__":
    print(f"\n{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.BOLD}{ConsoleColors.GREEN}  SHA-256 HASH REPORT GENERATOR v2.34{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.BOLD}  SINGLE REPORT MODE - Individual File Hash Report{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}\n")

    # Проверка за Unicode шрифтове
    if UNICODE_FONT_AVAILABLE:
        print(f"{ConsoleColors.GREEN}✓ Unicode font support enabled{ConsoleColors.RESET}")
    else:
        print(f"{ConsoleColors.YELLOW}⚠ Unicode font not available - some symbols may not display correctly{ConsoleColors.RESET}")

    print(f"{ConsoleColors.CYAN}✓ wordWrap='WORD' configured for European languages (German, English, Bulgarian){ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ Full timestamp fields (no truncation){ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ Dual RFC 3161 START/END + 3 TSA alternatives + millisecond timing{ConsoleColors.RESET}\n")

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("SingleReportGenerator")

    generator = SingleReportGenerator(logger, include_ots=False)

    if len(sys.argv) > 1:
        eml_path = Path(sys.argv[1])
    else:
        eml_path = Path(input("Enter file path: ").strip())

    if not eml_path.exists():
        print(f"{FileIcons.ERROR} File not found: {eml_path}")
        sys.exit(1)

    # Генериране на индивидуален отчет (със собствен уникален timestamp)
    file_info = generator.get_file_info(eml_path)
    if file_info:
        output_dir = eml_path.parent
        identity = generator._create_report_identity()
        pdf_name = generator._get_report_name(file_info, "individual", identity)
        output_file = output_dir / pdf_name

        # Unique timestamp + UUID-backed Report ID: never delete an older report.
        result = generator.generate(
            file_info, str(output_file), None, True, report_identity=identity)
        if result:
            print(f"{FileIcons.SUCCESS} Individual report created: {output_file.name}")
        else:
            print(f"{FileIcons.ERROR} Failed to create individual report")
            sys.exit(1)
    else:
        print(f"{FileIcons.ERROR} Could not read file information")
        sys.exit(1)

    print(f"\n{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.GREEN}✅ Processing complete!{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
