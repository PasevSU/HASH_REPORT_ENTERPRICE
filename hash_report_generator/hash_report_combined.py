#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SHA-256 HASH REPORT GENERATOR v2.34 - COMBINED REPORT
═══════════════════════════════════════════════════════════════════════════════

Генерира комбиниран SHA-256 хеш отчет за множество файлове от evidence package.
Използва споделеното ядро от hash_report_core.py.

ФИКС v2.34:
  - START/END TimeStampResp (.tsr) са binary embedded attachments в PDF; Base64 страниците са премахнати
  - Total Checksum е изведен като RFC3161-style bullet block без таблица
  - Пълна Unicode поддръжка за timestamp секцията с автоматично откриване на шрифтове
  - Премахнато съкращаване на всички полета (Nonce, Hash, Data, Signature)
  - 7-колонна таблица с "Modified" в комбинирания отчет
  - Коригиран wordWrap='WORD' за правилно пренасяне на думи при европейски езици
  - Подобрена класификация на артефактите (40+ типа файлове)
  - Уникален RFC 3161 timestamp за всеки отчет
  - RFC 3161 START/END с primary + 3 резервни TSA endpoints
  - Всички размери в PDF са само в KB; всички локални времена са до милисекунда
  - Име на PDF: YYYY-MM-DD-HHMMSSmmm_-_REPORTID-HASHREPORT.pdf; без презаписване
"""

import sys
import os
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging
import traceback
import time

_report_dir = Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if _report_path not in sys.path:
        sys.path.insert(0, _report_path)

# Импорт на споделеното ядро
from combined_table_layout import index_cell, size_kb_cell, digest_cell
from hash_report_core import (
    HashGeneratorCore,
    ReportConstants,
    ConsoleColors,
    FileIcons,
    NumberedCanvas,
    UNICODE_FONT_NAME,
    UNICODE_FONT_AVAILABLE,
    REPORTLAB_AVAILABLE,
    REPARSE_POINT,
    describe_read_error,
    file_attributes,
    install_requirements
)

# v5.5.0: progress heartbeat (stall fix) and the filter grammar shared with the
# Selection panel. Both are stdlib-only siblings of this script.
import progress_heartbeat
import file_filters

# Допълнителни импорти за PDF
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from hash_report_generator.a4_document import A4DocTemplate
from hash_report_generator.pdf_object_rules import _STYLE


class CombinedReportGenerator(HashGeneratorCore):
    """
    Генератор на комбинирани SHA-256 хеш отчети.
    Поддържа откриване на всички артефакти от evidence package.
    Наследява общата функционалност от HashGeneratorCore.
    """
    
    def __init__(self, logger, include_ots=True):
        """
        Инициализира генератора за комбинирани отчети.
        
        Args:
            logger: Logger инстанция
            include_ots: Дали да включва OTS информация
        """
        super().__init__(logger, include_ots)
    
    # ========================================================================
    # КЛАСИФИКАЦИЯ НА АРТЕФАКТИ
    # ========================================================================
    def _get_type_priority(self, file_type: str) -> int:
        """Връща приоритет на типа файл за сортиране"""
        priorities = {
            "ORIGINAL EML": 1,
            "CORE JSON": 2,
            "ROUTING": 3,
            "ATTACHMENTS JSON": 4,
            "DEEP FORENSIC": 5,
            "ADVANCED FORENSICS": 6,
            "FILESYSTEM": 7,
            "PRESERVATION": 8,
            "TIMELINE": 9,
            "THREAT MATRIX": 10,
            "ENTERPRISE SUMMARY": 11,
            "MANIFEST": 12,
            "TIMESTAMPS": 13,
            "CHAIN OF CUSTODY": 14,
            "ANOMALIES": 15,
            "DNS ANALYSIS": 16,
            "EVIDENCE ID": 17,
            "FORENSIC REPORT": 18,
            "BATCH FORENSIC REPORT": 19,
            "RAW EML TEXT": 20,
            "RAW HEADERS": 21,
            "EXTRACTED TEXT": 22,
            "HTML EXTRACTED": 23,
            "HTML ANALYSIS": 24,
            "PDF PROOF": 25,
            "INDIVIDUAL REPORT": 26,
            "COMBINED REPORT": 27,
            "DECODED PART": 28,
            "RAW PART": 29,
            "SHA256 HASH": 30,
            "SIGNATURE": 31,
            "ATTACHMENT (DANGEROUS)": 32,
            "ATTACHMENT (PDF)": 33,
            "ATTACHMENT (OFFICE)": 34,
            "ATTACHMENT (IMAGE)": 35,
            "ATTACHMENT (TEXT)": 36,
            "ATTACHMENT": 37,
            "JSON ARTIFACT": 40,
            "TEXT": 41,
            "BINARY": 42,
            "OTHER": 99,
        }
        return priorities.get(file_type, 99)
    
    def _classify_artifact_file(self, filename: str, base_name: str) -> str:
        """
        ENTERPRISE класификация на артефактни файлове.
        Разпознава всички файлове, генерирани от ParsedEML.py и HashGenerator.
        Поддържа 40+ типа файлове.
        """
        name_lower = filename.lower()
        
        # ═══════════════════════════════════════════════════════════════════
        # ОСНОВНИ ТИПОВЕ ФАЙЛОВЕ
        # ═══════════════════════════════════════════════════════════════════
        
        # Оригинален EML (ако не е част от ParsedEML артефактите)
        if filename.endswith('.eml') and not name_lower.startswith(f"{base_name}.eml.de"):
            return "ORIGINAL EML"
        
        # Сигнатура
        if filename.endswith('.sig'):
            return "SIGNATURE"
        
        # Хеш файл
        if filename.endswith('.sha256'):
            return "SHA256 HASH"
        
        # ═══════════════════════════════════════════════════════════════════
        # PDF ФАЙЛОВЕ
        # ═══════════════════════════════════════════════════════════════════
        if filename.endswith('.pdf'):
            if 'combined' in name_lower:
                return "COMBINED REPORT"
            elif 'individual' in name_lower:
                return "INDIVIDUAL REPORT"
            elif 'hash_report' in name_lower:
                if 'combined' in name_lower:
                    return "COMBINED REPORT"
                else:
                    return "INDIVIDUAL REPORT"
            else:
                return "PDF PROOF"
        
        # ═══════════════════════════════════════════════════════════════════
        # ТЕКСТОВИ ФАЙЛОВЕ
        # ═══════════════════════════════════════════════════════════════════
        if filename.endswith('.txt'):
            if 'raw_eml' in name_lower:
                return "RAW EML TEXT"
            elif 'extracted' in name_lower:
                return "EXTRACTED TEXT"
            elif 'main.txt' in name_lower:
                return "RAW EML TEXT"
            else:
                return "TEXT"
        
        # ═══════════════════════════════════════════════════════════════════
        # HTML ФАЙЛОВЕ
        # ═══════════════════════════════════════════════════════════════════
        if filename.endswith('.html') and 'analysis' not in name_lower:
            return "HTML EXTRACTED"
        
        # ═══════════════════════════════════════════════════════════════════
        # БИНАРНИ ФАЙЛОВЕ
        # ═══════════════════════════════════════════════════════════════════
        if filename.endswith('.bin'):
            if 'raw_headers' in name_lower:
                return "RAW HEADERS"
            elif 'decoded' in name_lower:
                return "DECODED PART"
            else:
                return "BINARY"
        
        # ═══════════════════════════════════════════════════════════════════
        # RAW ЧАСТИ (без разширение или с _raw)
        # ═══════════════════════════════════════════════════════════════════
        if '.part_' in name_lower and ('_raw' in name_lower or name_lower.endswith('_raw')):
            return "RAW PART"
        
        # ═══════════════════════════════════════════════════════════════════
        # JSON АРТЕФАКТИ - ПЪЛНА ГАМА ОТ ParsedEML.py
        # ═══════════════════════════════════════════════════════════════════
        if filename.endswith('.json'):
            # Основни JSON артефакти
            if 'core' in name_lower:
                return "CORE JSON"
            elif 'routing' in name_lower:
                return "ROUTING"
            elif 'attachments' in name_lower:
                return "ATTACHMENTS JSON"
            elif 'deep_forensic' in name_lower:
                return "DEEP FORENSIC"
            elif 'advanced-forensics' in name_lower or 'advanced_forensics' in name_lower:
                return "ADVANCED FORENSICS"
            elif 'filesystem' in name_lower:
                return "FILESYSTEM"
            elif 'preservation' in name_lower:
                return "PRESERVATION"
            elif 'timeline' in name_lower:
                return "TIMELINE"
            elif 'threat-matrix' in name_lower or 'threat_matrix' in name_lower:
                return "THREAT MATRIX"
            elif 'enterprise-summary' in name_lower or 'enterprise_summary' in name_lower:
                return "ENTERPRISE SUMMARY"
            elif 'manifest' in name_lower:
                return "MANIFEST"
            elif 'timestamps' in name_lower:
                return "TIMESTAMPS"
            elif 'chain-of-custody' in name_lower or 'chain_of_custody' in name_lower:
                return "CHAIN OF CUSTODY"
            
            # Анализ и детекция
            elif 'anomalies' in name_lower:
                return "ANOMALIES"
            elif 'dns_analysis' in name_lower or 'dns-analysis' in name_lower:
                return "DNS ANALYSIS"
            elif 'evidence_id' in name_lower:
                return "EVIDENCE ID"
            elif 'forensic_report' in name_lower:
                return "FORENSIC REPORT"
            elif 'batch_forensic' in name_lower:
                return "BATCH FORENSIC REPORT"
            elif 'html_analysis' in name_lower:
                return "HTML ANALYSIS"
            else:
                return "JSON ARTIFACT"
        
        # ═══════════════════════════════════════════════════════════════════
        # ПРИКРЕПЕНИ ФАЙЛОВЕ (от attachments директория)
        # ═══════════════════════════════════════════════════════════════════
        if 'attachments/' in filename or filename.startswith('attachments'):
            ext = Path(filename).suffix.lower()
            if ext in ['.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.scr', '.hta']:
                return "ATTACHMENT (DANGEROUS)"
            elif ext == '.pdf':
                return "ATTACHMENT (PDF)"
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico']:
                return "ATTACHMENT (IMAGE)"
            elif ext in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp']:
                return "ATTACHMENT (OFFICE)"
            elif ext in ['.txt', '.log', '.csv', '.md', '.json', '.xml', '.ini', '.cfg']:
                return "ATTACHMENT (TEXT)"
            else:
                return "ATTACHMENT"
        
        return "OTHER"
    
    # ========================================================================
    # ОТКРИВАНЕ НА ВСИЧКИ АРТЕФАКТИ
    # ========================================================================
    def _discover_all_files_from_eml_folder(self, eml_path: Path) -> List[Dict]:
        """
        ENTERPRISE универсално откриване на ВСИЧКИ файлове в evidence package.
        """
        files_for_report = []
        output_dir = eml_path.parent
        
        eml_stem = eml_path.stem
        if eml_stem.lower().endswith('.eml'):
            eml_stem = eml_stem[:-4]
        
        base_name = self._sanitize_filename_for_display(eml_stem)
        base_name_no_at = base_name.replace('@', '_')
        base_name_with_at = base_name.replace('_', '@')
        
        seen_paths = set()
        
        print(f"\n{FileIcons.SEARCH} {'='*60}")
        print(f"{FileIcons.SEARCH} ENTERPRISE ARTIFACT DISCOVERY")
        print(f"{FileIcons.SEARCH} Base name: {base_name}")
        print(f"{FileIcons.SEARCH} {'='*60}")
        
        # Стратегия 1: {base_name}.*
        for pattern in [f"{base_name}*", f"{base_name_no_at}*", f"{base_name_with_at}*"]:
            for file_path in output_dir.glob(pattern):
                if file_path.is_file() and str(file_path) not in seen_paths:
                    if '_hash_report_combined.pdf' in file_path.name:
                        continue
                    if file_path.name == eml_path.name:
                        continue
                    
                    seen_paths.add(str(file_path))
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.sha256(f.read()).hexdigest()
                        stat = file_path.stat()
                        created, modified = self._times_from_stat(stat)
                        
                        file_type = self._classify_artifact_file(file_path.name, base_name)
                        
                        files_for_report.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "hash": file_hash,
                            "size": stat.st_size,
                            "size_kb": stat.st_size / 1024,
                            "created": created,
                            "modified": modified,
                            "type": file_type
                        })
                        print(f"  {FileIcons.get_icon_by_type(file_type)} {file_path.name[:70]}... -> {file_type}")
                    except Exception as e:
                        self.logger.warning(f"Could not read {file_path.name}: {e}")
        
        # Оригинален EML
        if str(eml_path) not in seen_paths:
            try:
                with open(eml_path, 'rb') as f:
                    eml_hash = hashlib.sha256(f.read()).hexdigest()
                stat = eml_path.stat()
                created, modified = self._times_from_stat(stat)
                files_for_report.append({
                    "name": eml_path.name,
                    "path": str(eml_path),
                    "hash": eml_hash,
                    "size": stat.st_size,
                    "size_kb": stat.st_size / 1024,
                    "created": created,
                    "modified": modified,
                    "type": "ORIGINAL EML"
                })
                seen_paths.add(str(eml_path))
                print(f"  {FileIcons.EML} {eml_path.name} -> ORIGINAL EML")
            except Exception as e:
                self.logger.warning(f"Could not read EML file: {e}")
        
        # Attachments директория
        for base_variant in [base_name, base_name_no_at, base_name_with_at]:
            attachments_dir = output_dir / f"{base_variant}.eml.attachments"
            if attachments_dir.exists():
                print(f"  {FileIcons.FOLDER} Scanning attachments: {attachments_dir.name}")
                for att_file in attachments_dir.glob("*"):
                    if att_file.is_file() and str(att_file) not in seen_paths:
                        seen_paths.add(str(att_file))
                        try:
                            with open(att_file, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                            stat = att_file.stat()
                            created, modified = self._times_from_stat(stat)
                            
                            ext = att_file.suffix.lower()
                            if ext in ['.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js']:
                                file_type = "ATTACHMENT (DANGEROUS)"
                            elif ext == '.pdf':
                                file_type = "ATTACHMENT (PDF)"
                            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg']:
                                file_type = "ATTACHMENT (IMAGE)"
                            elif ext in ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']:
                                file_type = "ATTACHMENT (OFFICE)"
                            elif ext in ['.txt', '.log', '.csv']:
                                file_type = "ATTACHMENT (TEXT)"
                            else:
                                file_type = "ATTACHMENT"
                            
                            files_for_report.append({
                                "name": f"attachments/{att_file.name}",
                                "path": str(att_file),
                                "hash": file_hash,
                                "size": stat.st_size,
                                "size_kb": stat.st_size / 1024,
                                "created": created,
                                "modified": modified,
                                "type": file_type
                            })
                            print(f"    {FileIcons.FILE} {att_file.name} -> {file_type}")
                        except Exception as e:
                            self.logger.warning(f"Could not read attachment {att_file.name}: {e}")
        
        # Специфични файлове
        specific_files = [
            (f"{base_name}.eml.sig", "SIGNATURE"),
            (f"{base_name_no_at}.eml.sig", "SIGNATURE"),
            (f"{base_name}.pdf", "PDF PROOF"),
            (f"{base_name_no_at}.pdf", "PDF PROOF"),
            (f"{base_name}.eml.main.txt", "RAW EML TEXT"),
            (f"{base_name_no_at}.eml.main.txt", "RAW EML TEXT"),
        ]
        
        for filename, file_type in specific_files:
            file_path = output_dir / filename
            if file_path.exists() and str(file_path) not in seen_paths:
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    stat = file_path.stat()
                    created, modified = self._times_from_stat(stat)
                    files_for_report.append({
                        "name": filename,
                        "path": str(file_path),
                        "hash": file_hash,
                        "size": stat.st_size,
                        "size_kb": stat.st_size / 1024,
                        "created": created,
                        "modified": modified,
                        "type": file_type
                    })
                    seen_paths.add(str(file_path))
                    icon = FileIcons.SIG if 'sig' in filename else FileIcons.PDF if filename.endswith('.pdf') else FileIcons.TXT
                    print(f"  {icon} {filename} -> {file_type}")
                except Exception as e:
                    self.logger.warning(f"Could not read {filename}: {e}")
        
        # Всички JSON файлове
        for json_file in output_dir.glob("*.json"):
            if str(json_file) not in seen_paths:
                try:
                    with open(json_file, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                    stat = json_file.stat()
                    created, modified = self._times_from_stat(stat)
                    file_type = self._classify_artifact_file(json_file.name, base_name)
                    
                    files_for_report.append({
                        "name": json_file.name,
                        "path": str(json_file),
                        "hash": file_hash,
                        "size": stat.st_size,
                        "size_kb": stat.st_size / 1024,
                        "created": created,
                        "modified": modified,
                        "type": file_type
                    })
                    seen_paths.add(str(json_file))
                    print(f"  {FileIcons.JSON} {json_file.name} -> {file_type}")
                except Exception as e:
                    self.logger.warning(f"Could not read {json_file.name}: {e}")
        
        # Сортиране по тип и име
        files_for_report.sort(key=lambda x: (self._get_type_priority(x['type']), x['name']))
        
        print(f"\n{FileIcons.SUCCESS} {'='*60}")
        print(f"{FileIcons.SUCCESS} DISCOVERY COMPLETE")
        print(f"{FileIcons.SUCCESS} {'='*60}")
        print(f"  Total files found: {len(files_for_report)}")
        
        type_stats = {}
        for f in files_for_report:
            t = f['type']
            type_stats[t] = type_stats.get(t, 0) + 1
        
        print(f"\n  Files by type:")
        for t, count in sorted(type_stats.items()):
            print(f"    {FileIcons.get_icon_by_type(t)} {t}: {count}")
        
        if self.logger:
            self.logger.info(f"Discovered {len(files_for_report)} files from evidence package")
        
        return files_for_report
    
    # ========================================================================
    # ГЕНЕРИРАНЕ НА КОМБИНИРАН ОТЧЕТ
    # ========================================================================
    def generate(self, files_info: List[Dict], output_path: str,
                 include_explanatory: bool = False,
                 report_identity: Optional[Dict] = None,
                 selection_filters: Optional[List[str]] = None) -> bool:
        """
        Генерира комбиниран отчет с START/STOP RFC 3161 timestamps и 7 колони.
        
        Args:
            files_info: Списък с информация за файловете
            output_path: Път за запазване на PDF
            include_explanatory: Дали да включи пояснителен документ
            
        Returns:
            bool: True при успех, False при грешка
        """
        try:
            print(f"\n{ConsoleColors.CYAN}{'─'*60}{ConsoleColors.RESET}")
            print(f"{FileIcons.REPORT} Generating COMBINED hash report...")
            print(f"{ConsoleColors.CYAN}{'─'*60}{ConsoleColors.RESET}")
            progress_heartbeat.phase('pdf-prepare', note=f'{len(files_info)} file(s)')
            
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
            
            # START RFC 3161: existing evidence-set timestamp becomes the opening marker.
            evidence_sha256 = self._generate_checksum(files_info)
            process_start_ns = time.perf_counter_ns()
            rfc3161_timestamp = self._get_rfc3161_timestamp(
                message_imprint=evidence_sha256, force_new=True, marker_label='START')
            
            # Системна информация
            self._add_system_info_section(story, styles, now, timezone_str, report_id, 
                                          files_info=files_info, single_file=False,
                                          rfc3161_timestamp=rfc3161_timestamp,
                                          selection_filters=selection_filters)
            story.append(Spacer(1, ReportConstants.SPACER_BEFORE_TABLE))
            
            # Таблица с файлове - 7 колони включително Modified
            story.append(Paragraph("<b>Evidence Package Files Information:</b>", styles['normal_style']))
            story.append(Spacer(1, ReportConstants.SPACER_TABLE))
            
            # Стилове за таблицата с правилен wordWrap
            # Central rules: Unicode (UTF-8 capable) fonts and white header text.
            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            from hash_report_generator.pdf_object_rules import font_name, combined_cell_paragraph_styles
            regular_font, bold_font = font_name('regular'), font_name('bold')
            registerFontFamily(regular_font, normal=regular_font, bold=bold_font,
                               italic=regular_font, boldItalic=bold_font)
            cell_styles = combined_cell_paragraph_styles(styles, ReportConstants)
            safe_style, hash_style, header_style = (
                cell_styles['safe'], cell_styles['hash'], cell_styles['header'])
            safe_style.fontName = hash_style.fontName = regular_font
            header_style.fontName = bold_font
            
            # Заглавия на 7-те колони
            table_data = [[
                Paragraph("<b>#</b>", header_style),
                Paragraph("<b>File Name</b>", header_style),
                Paragraph("<b>Type</b>", header_style),
                Paragraph("<b>Size (KB)</b>", header_style),
                Paragraph("<b>Created</b>", header_style),
                Paragraph("<b>Modified</b>", header_style),  # Нова колона
                Paragraph("<b>SHA-256 Hash</b>", header_style)
            ]]
            
            idx = 1
            progress_heartbeat.phase('table', total=len(files_info))
            for file_info in sorted(files_info, key=lambda x: (self._get_type_priority(x['type']), x['name'])):
                progress_heartbeat.tick()
                display_name = self._sanitize_filename_for_display(file_info['name'])
                
                size_text = self._format_kb(file_info['size'])
                created_date = self._format_datetime_plain_ms(file_info['created'])
                modified_date = self._format_datetime_plain_ms(file_info['modified'])
                file_type = file_info['type']
                
                status = _STYLE['STATUS_COLORS']
                if file_type == "ORIGINAL EML":
                    name_cell = Paragraph(f"<font color='{status['primary']}'><b>{display_name}</b></font>", safe_style)
                    type_cell = Paragraph(f"<b>{file_type}</b>", safe_style)
                elif "DANGEROUS" in file_type:
                    name_cell = Paragraph(f"<font color='{status['error']}'><b>⚠️ {display_name}</b></font>", safe_style)
                    type_cell = Paragraph(f"<font color='{status['error']}'><b>{file_type}</b></font>", safe_style)
                else:
                    name_cell = Paragraph(display_name, safe_style)
                    type_cell = Paragraph(file_type, safe_style)
                
                table_data.append([
                    index_cell(idx, safe_style),
                    name_cell,
                    type_cell,
                    Paragraph(size_kb_cell(size_text), safe_style),
                    Paragraph(created_date, safe_style),
                    Paragraph(modified_date, safe_style),
                    digest_cell(file_info['hash'], hash_style)
                ])
                idx += 1
            
            # Ширини на 7-те колони
            col_widths = [
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['number'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['name'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['type'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['size'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['created'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['modified'],
                self.table_width * ReportConstants.COMBINED_TABLE_COL_PROPORTIONS_7['hash']
            ]
            
            table = Table(table_data, repeatRows=1, colWidths=col_widths)
            from hash_report_generator.pdf_object_rules import globalize_table
            globalize_table(table, alignments='combined')

            story.append(table)
            story.append(Spacer(1, ReportConstants.SPACER_AFTER_TABLE))
            
            # Обобщена статистика
            total_size_bytes = sum(f['size'] for f in files_info)
            
            type_stats = {}
            for file_info in files_info:
                t = file_info['type']
                type_stats[t] = type_stats.get(t, 0) + 1
            
            stats_text = f"<b>Evidence Package Summary:</b><br/>"
            stats_text += f"• Total files in package: {len(files_info)}<br/>"
            stats_text += f"• Total package size: {self._format_kb(total_size_bytes)}<br/>"
            stats_text += f"<br/><b>Files by type:</b><br/>"
            
            for t, count in sorted(type_stats.items()):
                if count > 0:
                    stats_text += f"  • {t}: {count}<br/>"
            
            story.append(Paragraph(stats_text, styles['normal_style']))
            story.append(Spacer(1, ReportConstants.SPACER_SECTION))
            
            # END RFC 3161 immediately closes the actual report.
            # The explanatory document is generated separately and is never placed
            # between START and END.
            # END RFC 3161: cryptographically close the same report-generation interval.
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
            self._add_legal_declaration(story, styles, now, timezone_str, is_combined=True)
            self._add_footer(story, styles, now, timezone_str, is_combined=True)

            # v2.34: no visible Base64 block. Original START/END TimeStampResp
            # standalone generator artifacts may be attached after ReportLab build; ChronoSeal report-only mode delegates final DSS embedding.
            progress_heartbeat.phase('pdf-build', note=f'{len(files_info)} row(s)')
            doc.build(story, canvasmaker=NumberedCanvas)
            progress_heartbeat.note('pdf-build complete')
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
                report_id=report_id, report_type='COMBINED', generated_at=now,
                timezone_label=timezone_str, output_pdf=output_path, files_info=files_info,
                evidence_sha256=evidence_sha256, start_timestamp_text=rfc3161_timestamp,
                end_timestamp_text=end_timestamp, end_message_imprint=end_imprint,
                start_anchor_type=start_anchor_type, processing_duration_ms=duration_ms,
                embedded_pdf_artifacts=embedded_rfc3161, explanatory_pdf=explanatory_path,
            )
            if db_result:
                print(f"{FileIcons.SUCCESS} SQLite evidence database: {Path(db_result['path']).name}")
                print(f"  SHA-256: {db_result['sha256']}")
            else:
                print(f"{FileIcons.WARNING} SQLite evidence database could not be updated")
            
            file_size_kb = os.path.getsize(output_path) / 1024
            print(f"{FileIcons.SUCCESS} Combined report created: {os.path.basename(output_path)} ({len(files_info)} files, {file_size_kb:.0f} KB)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating combined PDF: {e}")
            traceback.print_exc()
            return False
    
    # ========================================================================
    # ПУБЛИЧЕН МЕТОД ЗА ГЕНЕРИРАНЕ ОТ ПАПКА
    # ========================================================================
    # ========================================================================
    # DISCOVERY: BOUNDED, DETERMINISTIC, EVIDENCE-SAFE
    # ========================================================================
    @staticmethod
    def _env_flag(name) -> bool:
        return os.environ.get(name, '').strip().lower() in ('1', 'true', 'yes', 'on')

    @staticmethod
    def _is_link(path: Path) -> bool:
        """True for a symlink or any Win32 reparse point (junction, cloud link)."""
        try:
            if path.is_symlink():
                return True
            return bool(file_attributes(path) & REPARSE_POINT)
        except OSError:
            return False

    def _iter_evidence_files(self, folder_path, recursive, follow_links, skipped):
        """Yield candidate files in a deterministic order, inside the selected root.

        Symlinked/junction directories are not descended into by default: following
        them silently widens the evidence set beyond the folder the operator chose
        (OneDrive known-folder links, junctions to other drives) and is also where
        most unreadable cloud placeholders live.
        """
        if not recursive:
            for entry in sorted(folder_path.iterdir(), key=lambda p: p.name.lower()):
                if entry.is_dir():
                    continue
                if not follow_links and self._is_link(entry):
                    skipped.append({'path': str(entry), 'reason': 'symbolic link or reparse point'})
                    print(f"  {FileIcons.INFO} Skipping linked file: {entry.name}")
                    continue
                if entry.is_file():
                    yield entry
            return
        for dirpath, dirnames, filenames in os.walk(folder_path, followlinks=follow_links):
            if not follow_links:
                kept = []
                for name in sorted(dirnames, key=str.lower):
                    candidate = Path(dirpath) / name
                    if self._is_link(candidate):
                        skipped.append({'path': str(candidate), 'reason': 'linked directory (not followed)'})
                        print(f"  {FileIcons.INFO} Skipping linked directory: {candidate}")
                        continue
                    kept.append(name)
                dirnames[:] = kept
            else:
                dirnames.sort(key=str.lower)
            for name in sorted(filenames, key=str.lower):
                candidate = Path(dirpath) / name
                if not follow_links and self._is_link(candidate):
                    skipped.append({'path': str(candidate), 'reason': 'symbolic link or reparse point'})
                    print(f"  {FileIcons.INFO} Skipping linked file: {candidate}")
                    continue
                yield candidate

    @staticmethod
    def _write_unreadable_audit(folder_path, unreadable, skipped, recursive,
                                filters=None, excluded_by_filter=0):
        """Record every excluded file so the evidence case is self-describing.

        v5.5.0: the active file-type filters are recorded too, so a report that
        covers only part of a folder is reproducible from its own evidence.
        """
        evidence_dir = (os.environ.get('CHRONOSEAL_EVIDENCE_DIR') or '').strip()
        target_dir = Path(evidence_dir) if evidence_dir else Path(folder_path)
        if not target_dir.is_dir():
            return None
        payload = {
            'schema': 'chronoseal.discovery-unreadable/v1',
            'root': str(folder_path),
            'recursive': bool(recursive),
            'unreadable_count': len(unreadable),
            'skipped_link_count': len(skipped),
            'unreadable_files': unreadable,
            'skipped_links': skipped,
            'excluded_by_filter_count': int(excluded_by_filter or 0),
            'note': ('These paths could not be hashed or were not followed. They are NOT part of '
                     'the report evidence set; the list is retained for auditability.'),
        }
        payload.update(file_filters.audit_payload(filters))
        target = target_dir / 'discovery-unreadable.json'
        tmp = target.with_name(target.name + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, target)
        return target

    def _discover_all_files_from_folder(self, folder_path: Path, exclude_paths=None,
                                        recursive: bool = False, filters=None) -> List[Dict]:
        """Discover and hash every regular file below an arbitrary folder.

        Folder mode does not require an EML file. Paths are stored relative to the
        selected root so nested evidence packages remain unambiguous.

        An evidence report must never silently omit a file it was asked to cover:
        unreadable files therefore fail the run unless the operator explicitly
        opts in with ``generator.allow_unreadable_files`` (env
        ``CHRONOSEAL_ALLOW_UNREADABLE_FILES``), in which case they are recorded in
        ``discovery-unreadable.json`` inside the evidence case.
        """
        folder_path = Path(folder_path).resolve()
        excluded = {Path(p).resolve() for p in (exclude_paths or [])}
        files_for_report = []
        unreadable = []
        skipped = []
        allow_unreadable = self._env_flag('CHRONOSEAL_ALLOW_UNREADABLE_FILES')
        follow_links = self._env_flag('CHRONOSEAL_FOLLOW_LINKS')
        # v5.5.0: the operator may narrow the evidence set by file type. The
        # list arrives as JSON in the environment (CHRONOSEAL_INCLUDE_PATTERNS)
        # so the generator stays a stand-alone script with no ChronoSeal imports.
        filters = file_filters.parse(filters if filters is not None else file_filters.from_env())
        excluded_by_filter = 0

        print(f"\n{FileIcons.SEARCH} {'='*60}")
        print(f"{FileIcons.SEARCH} GENERIC FOLDER DISCOVERY")
        print(f"{FileIcons.SEARCH} Root: {folder_path}")
        print(f"{FileIcons.SEARCH} Recursive: {bool(recursive)}; follow links: {follow_links}")
        print(f"{FileIcons.SEARCH} File type filters: {file_filters.describe(filters)}")
        print(f"{FileIcons.SEARCH} {'='*60}")
        progress_heartbeat.phase('discovery', note=file_filters.describe(filters))

        for file_path in self._iter_evidence_files(folder_path, recursive, follow_links, skipped):
            progress_heartbeat.tick()
            resolved = file_path.resolve()
            if resolved in excluded:
                continue
            if self._is_generated_hash_report(file_path):
                print(f"  {FileIcons.INFO} Skipping generated hash report: {file_path.name}")
                continue
            # Filters run after the self-exclusion rule: a generated report or an
            # evidence artefact is never re-admitted just because it matches.
            try:
                rel_for_filter = file_path.relative_to(folder_path).as_posix()
            except ValueError:
                rel_for_filter = file_path.name
            if not file_filters.matches(file_path.name, rel_for_filter, filters):
                excluded_by_filter += 1
                continue

            try:
                rel_name = file_path.relative_to(folder_path).as_posix()
                stat = file_path.stat()
                created, modified = self._times_from_stat(stat)
                file_hash = self.calculate_sha256(file_path)
                if not re.fullmatch(r'[0-9a-fA-F]{64}', file_hash or ''):
                    raise OSError(0, 'hash function returned no digest')

                file_type = self._classify_artifact_file(rel_name, folder_path.name)
                files_for_report.append({
                    "name": rel_name,
                    "path": str(file_path),
                    "hash": file_hash,
                    "size": stat.st_size,
                    "size_kb": stat.st_size / 1024,
                    "created": created,
                    "modified": modified,
                    "type": file_type,
                })
                print(f"  {FileIcons.get_icon_by_type(file_type)} {rel_name} -> {file_type}")
            except Exception as e:
                info = describe_read_error(file_path, e)
                unreadable.append({
                    'path': str(file_path),
                    'name': file_path.name,
                    'reason': info['reason'],
                    'remedy': info['remedy'],
                    'errno': info['errno'],
                    'winerror': info['winerror'],
                    'file_attributes': info['file_attributes'],
                    'error': f'{type(e).__name__}: {e}',
                })
                self.logger.warning(f"Could not read {file_path}: {e} [{info['reason']}]")

        files_for_report.sort(key=lambda x: (self._get_type_priority(x['type']), x['name'].lower()))
        progress_heartbeat.phase('discovery-done', total=len(files_for_report),
                                 note=f'{excluded_by_filter} filtered out')
        audit_path = self._write_unreadable_audit(folder_path, unreadable, skipped, recursive,
                                                  filters=filters,
                                                  excluded_by_filter=excluded_by_filter)
        if audit_path:
            print(f"{FileIcons.INFO} Discovery audit: {audit_path}")
        if excluded_by_filter:
            print(f"{FileIcons.INFO} File type filters excluded {excluded_by_filter} file(s); "
                  f"{len(files_for_report)} selected")

        if unreadable or skipped:
            summary = (f"{len(unreadable)} unreadable file(s), {len(skipped)} link(s) not followed")
            if unreadable and not allow_unreadable:
                # Fail closed: a PASS report that silently omits evidence is worse
                # than no report at all.
                detail = '\n'.join(
                    f"  - {item['name']}: {item['reason']} (errno={item['errno']}); {item['remedy']}"
                    for item in unreadable[:15])
                more = '' if len(unreadable) <= 15 else f'\n  ... and {len(unreadable) - 15} more'
                raise RuntimeError(
                    'UNREADABLE_EVIDENCE_FILES: ' + summary +
                    ' cannot be hashed, so the report would silently omit them.\n' + detail + more +
                    '\nFix the listed files, exclude the folder from the evidence set, or set '
                    'generator.allow_unreadable_files=true to publish with an explicit exclusion list '
                    '(written to discovery-unreadable.json in the evidence case).')
            self.logger.warning('Discovery exclusions: ' + summary)
            print(f"{FileIcons.WARNING} Discovery exclusions: {summary}")

        if not files_for_report and filters:
            raise RuntimeError(
                'FILTER_MATCHED_NO_FILES: the file type filters matched no file below '
                f'{folder_path}.\n'
                f'  filters: {file_filters.describe(filters)}\n'
                f'  recursive: {bool(recursive)}; {excluded_by_filter} file(s) were excluded by the filters.\n'
                'Fix the filter patterns, enable "Include subfolders", or clear the filters.')

        print(f"\n{FileIcons.SUCCESS} Discovery complete: {len(files_for_report)} file(s)")
        return files_for_report

    def generate_from_folder(self, folder_path: Path, recursive: bool = False,
                             filters=None) -> Optional[Path]:
        """Generate one combined report for any folder; an EML file is optional.

        v5.5.0: ``filters`` narrows the evidence set by file type and a progress
        heartbeat keeps the parent watchdog informed during the silent phases.
        """
        folder_path = Path(folder_path)
        if not folder_path.is_dir():
            print(f"{FileIcons.ERROR} Folder not found: {folder_path}")
            return None

        progress_heartbeat.install()
        try:
            return self._generate_from_folder_inner(folder_path, recursive, filters)
        finally:
            progress_heartbeat.close()

    def _generate_from_folder_inner(self, folder_path: Path, recursive: bool,
                                    filters=None) -> Optional[Path]:
        identity = self._create_report_identity()
        target_path = folder_path / f"{identity['report_id']}_HASHREPORT_TYP_COMBO.pdf"
        # Resolve the selection once so the report records exactly what discovery used.
        filters = file_filters.parse(filters if filters is not None else file_filters.from_env())

        # The new name is unique. Older reports are preserved and excluded from
        # the evidence-set by _is_generated_hash_report().
        files_info = self._discover_all_files_from_folder(
            folder_path, exclude_paths=[target_path], recursive=recursive, filters=filters)
        if not files_info:
            print(f"{FileIcons.ERROR} No files found in folder: {folder_path}")
            return None

        if not self._verify_before_generate(files_info):
            print(f"{FileIcons.ERROR} Pre-generation hash verification failed")
            return None

        success = self.generate(files_info, str(target_path), True, report_identity=identity,
                                selection_filters=filters)
        if success and target_path.exists():
            print(f"\n{FileIcons.SUCCESS} Combined folder report created: {target_path.name}")
            print(f"  📊 Files included: {len(files_info)}")
            print(f"  📄 File size: {target_path.stat().st_size / 1024:.0f} KB")
            return target_path

        print(f"{FileIcons.ERROR} Combined report generation failed")
        return None

    # ========================================================================
    # ПУБЛИЧЕН МЕТОД ЗА ГЕНЕРИРАНЕ ОТ EML
    # ========================================================================
    def generate_from_eml(self, eml_path: Path) -> Optional[Path]:
        """
        Публичен метод за генериране на комбиниран отчет от EML файл.
        
        Args:
            eml_path: Път до EML файла
            
        Returns:
            Optional[Path]: Път до генерирания PDF или None при грешка
        """
        output_dir = eml_path.parent
        identity = self._create_report_identity()
        target_path = output_dir / f"{identity['report_id']}_HASHREPORT_TYP_COMBO.pdf"

        files_info = self._discover_all_files_from_eml_folder(eml_path)
        
        if len(files_info) <= 1:
            print(f"{FileIcons.WARNING} Only EML file found, no artifacts for combined report")
            return None
        
        success = self.generate(files_info, str(target_path), True, report_identity=identity)
        
        if success and target_path.exists():
            file_size_kb = target_path.stat().st_size / 1024
            print(f"\n{FileIcons.SUCCESS} Combined report created: {target_path.name}")
            print(f"  📊 Files included: {len(files_info)}")
            print(f"  📄 File size: {file_size_kb:.0f} KB")
            return target_path
        else:
            print(f"{FileIcons.ERROR} Combined report generation failed")
            return None


# ============================================================================
# САМОСТОЯТЕЛНО ИЗПЪЛНЕНИЕ - КОМБИНИРАН ОТЧЕТ
# ============================================================================
if __name__ == "__main__":
    print(f"\n{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.BOLD}{ConsoleColors.GREEN}  SHA-256 HASH REPORT GENERATOR v2.34{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.BOLD}  COMBINED REPORT MODE - Enterprise Package Support{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}\n")
    
    # Проверка за Unicode шрифтове
    if UNICODE_FONT_AVAILABLE:
        print(f"{ConsoleColors.GREEN}✓ Unicode font support enabled{ConsoleColors.RESET}")
    else:
        print(f"{ConsoleColors.YELLOW}⚠ Unicode font not available - some symbols may not display correctly{ConsoleColors.RESET}")
    
    print(f"{ConsoleColors.CYAN}✓ wordWrap='WORD' configured for European languages (German, English, Bulgarian){ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ 7-column table with 'Modified' column{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ Full timestamp fields (no truncation){ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ Dual RFC 3161 START/END + 3 TSA alternatives + millisecond timing{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}✓ 40+ artifact types supported{ConsoleColors.RESET}\n")
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("CombinedReportGenerator")
    
    generator = CombinedReportGenerator(logger, include_ots=False)
    
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path(input("Enter evidence package folder or EML file path: ").strip())
    
    if not input_path.exists():
        print(f"{FileIcons.ERROR} Path not found: {input_path}")
        sys.exit(1)
    
    # Folder mode is non-recursive by default. Recursion is explicit only.
    recursive = '--recursive' in sys.argv[2:]
    try:
        if input_path.is_dir():
            combined = generator.generate_from_folder(input_path, recursive=recursive)
        else:
            combined = generator.generate_from_eml(input_path)
    except RuntimeError as exc:
        # Includes UNREADABLE_EVIDENCE_FILES: fail closed without a traceback wall.
        print(f"{FileIcons.ERROR} {exc}")
        sys.exit(3)
    if not combined:
        print(f"{FileIcons.ERROR} No combined report generated (insufficient artifacts)")
        sys.exit(1)
    print(f"{FileIcons.SUCCESS} Combined report: {combined.name}")
    
    print(f"\n{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")
    print(f"{ConsoleColors.GREEN}✅ Processing complete!{ConsoleColors.RESET}")
    print(f"{ConsoleColors.CYAN}{'='*60}{ConsoleColors.RESET}")