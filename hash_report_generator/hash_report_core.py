#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SHA-256 HASH REPORT GENERATOR v2.34 - SHARED CORE
═══════════════════════════════════════════════════════════════════════════════

Споделено ядро за генериране на хеш отчети.
Съдържа общи константи, стилове, криптографски функции и базов клас.

ФИКС v2.34:
  - Реалният CMS SignerInfo TSA сертификат се идентифицира и валидира (EKU Time Stamping)
  - Certificate chain се проверява към genTime; DFN Community Root 2022 е pinned по SHA-256
  - CRL се открива от CRL Distribution Points и се проверяват подпис, freshness и revocation serial
  - OCSP се открива от AIA и се валидира по RFC 6960; network failure остава UNAVAILABLE
  - X.509 chain / CRL / OCSP validation artifacts се вграждат в PDF за offline re-validation
  - RFC 3161 START/END TimeStampResp (.tsr) се вграждат бинарно като PDF attachments
  - Видимите Base64 token блокове са премахнати; PDF остава самостоятелно проверим
  - Добавен е SHA-256 и размер в KB на всеки embedded TimeStampResp
  - Total Checksum е изведен като RFC3161-style bullet block без таблица
  - Пълна Unicode поддръжка за timestamp секцията с автоматично откриване на шрифтове
  - Премахнато съкращаване на всички полета (Nonce, Hash, Data, Signature)
  - Коригиран wordWrap='WORD' за правилно пренасяне на думи при европейски езици
  - Уникален RFC 3161 timestamp за всеки отчет
  - Fallback криптографски timestamp при недостъпен TSA сървър
  - Multi-hash Total Checksum: CRC32, CRC64/XZ, SHA-256, SHA-1, BLAKE2sp, MD5, XXH64, SHA-384, SHA-512, SHA3-256
  - Всички размери в PDF са показани само в KB (1 KB = 1024 bytes)
  - Всички локални времена в PDF са с точност до милисекунда
  - RFC 3161 автоматичен failover: DFN + 3 независими резервни TSA endpoints
  - Уникално име: YYYY-MM-DD-HHMMSSmmm_-_REPORTID-HASHREPORT.pdf; Report ID съвпада с PDF
"""

import os
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict, Union, Optional, Tuple
from datetime import datetime
import threading
import platform
import socket
import getpass
import uuid
import base64
import subprocess
import sys
import logging
import traceback
import struct
import time
import hmac
import tempfile
import shutil
import zlib

# Direct script/runpy imports must also resolve sibling report modules from
# unrelated working directories.
_report_dir = Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if _report_path not in sys.path:
        sys.path.insert(0, _report_path)

# The CLI emits Unicode status symbols. Use a loss-tolerant UTF-8 console on
# Windows legacy code pages while leaving non-reconfigurable streams untouched.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

# v5.5.0 defect fix: long phases used to run completely silently, so the pipeline
# watchdog could not tell "slow" apart from "stalled" and killed healthy runs.
# progress_heartbeat emits one short line at least every N seconds. Every call is
# optional: without the sibling module the generator behaves exactly as v5.4.0.
try:
    import progress_heartbeat as _heartbeat
except ImportError:  # pragma: no cover - standalone use without the sibling module
    _heartbeat = None


def _hb_phase(name, total=None, note=None):
    if _heartbeat is not None:
        _heartbeat.phase(name, total=total, note=note)


def _hb_tick(done=None, note=None):
    if _heartbeat is not None:
        _heartbeat.tick(done=done, note=note)


def _hb_note(text):
    if _heartbeat is not None:
        _heartbeat.note(text)


# ============================================================================
# ФУНКЦИЯ ЗА АВТОМАТИЧНО ИНСТАЛИРАНЕ НА ЗАВИСИМОСТИ
# ============================================================================
def install_requirements():
    """Инсталира необходимите Python пакети ако липсват"""
    requirements = ['requests', 'cryptography', 'pytz', 'reportlab', 'pypdf']
    for req in requirements:
        try:
            __import__(req.replace('-', '_'))
        except ImportError:
            print(f"Инсталиране на {req}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])

install_requirements()


# ============================================================================
# ИМПОРТ НА БИБЛИОТЕКИ С ПРОВЕРКА ЗА НАЛИЧНОСТ
# ============================================================================
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.pdfmetrics import registerFont, registerFontFamily
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not installed. PDF generation will not work.")

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: cryptography not installed. Some features will not work.")

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    print("Warning: pytz not installed. Using local timezone.")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Warning: requests not installed. Timestamp service will not work.")

try:
    from pypdf import PdfReader, PdfWriter
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    print("Warning: pypdf not installed. RFC 3161 responses cannot be embedded in PDF.")

try:
    if __package__:
        from .rfc3161_validation import validate_rfc3161_token
    else:
        from rfc3161_validation import validate_rfc3161_token
    RFC3161_VALIDATION_AVAILABLE = True
except ImportError as _rfc3161_validation_import_error:
    RFC3161_VALIDATION_AVAILABLE = False
    print(f"Warning: RFC 3161 chain/CRL/OCSP validation module unavailable: {_rfc3161_validation_import_error}")

try:
    if __package__:
        from .evidence_database import (
            DEFAULT_DB_FILENAME,
            build_record as build_database_record,
            save_record as save_database_record,
        )
    else:
        from evidence_database import (
            DEFAULT_DB_FILENAME,
            build_record as build_database_record,
            save_record as save_database_record,
        )
    EVIDENCE_DATABASE_AVAILABLE = True
except ImportError as _evidence_database_import_error:
    DEFAULT_DB_FILENAME = 'hash_report_evidence.sqlite3'
    EVIDENCE_DATABASE_AVAILABLE = False
    print(f"Warning: SQLite evidence database module unavailable: {_evidence_database_import_error}")


# ============================================================================
# UNICODE ШРИФТОВЕ ЗА PDF
# ============================================================================
def register_unicode_fonts():
    """
    Регистрира Unicode шрифтове за PDF поддръжка на специални символи.
    Търси системни шрифтове в Windows, Linux и macOS.
    """
    UNICODE_FONT = 'Helvetica'
    FONT_REGISTERED = False
    
    font_paths = [
        # Windows
        'C:/Windows/Fonts/DejaVuSans.ttf',
        'C:/Windows/Fonts/DejaVuSansCondensed.ttf',
        'C:/Windows/Fonts/Arial.ttf',
        'C:/Windows/Fonts/ARIALUNI.TTF',
        'C:/Windows/Fonts/consola.ttf',
        # Linux
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        '/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        # macOS
        '/Library/Fonts/Arial Unicode.ttf',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/Supplemental/Helvetica.ttf',
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
                UNICODE_FONT = 'UnicodeFont'
                FONT_REGISTERED = True
                print(f"✓ Registered Unicode font: {os.path.basename(font_path)}")
                break
            except Exception as e:
                continue
    
    if not FONT_REGISTERED:
        print("⚠️ No Unicode font found - using Helvetica (some symbols may not display correctly)")
    
    return UNICODE_FONT, FONT_REGISTERED

# Регистрираме Unicode шрифтове при стартиране
UNICODE_FONT_NAME, UNICODE_FONT_AVAILABLE = register_unicode_fonts()


# ============================================================================
# ЦВЕТОВЕ ЗА КОНЗОЛЕН ИЗХОД
# ============================================================================

class ConsoleColors:
    """Цветове за конзолен изход"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'


class FileIcons:
    """Икони за различни типове файлове в конзолата"""
    EML = f"{ConsoleColors.BLUE}📧{ConsoleColors.RESET}"
    JSON = f"{ConsoleColors.MAGENTA}📋{ConsoleColors.RESET}"
    PDF = f"{ConsoleColors.RED}📄{ConsoleColors.RESET}"
    TXT = f"{ConsoleColors.CYAN}📝{ConsoleColors.RESET}"
    BIN = f"{ConsoleColors.YELLOW}🔧{ConsoleColors.RESET}"
    SHA256 = f"{ConsoleColors.GREEN}🔐{ConsoleColors.RESET}"
    HTML = f"{ConsoleColors.CYAN}🌐{ConsoleColors.RESET}"
    SIG = f"{ConsoleColors.GREEN}✍️{ConsoleColors.RESET}"
    SUCCESS = f"{ConsoleColors.GREEN}✅{ConsoleColors.RESET}"
    ERROR = f"{ConsoleColors.RED}❌{ConsoleColors.RESET}"
    WARNING = f"{ConsoleColors.YELLOW}⚠️{ConsoleColors.RESET}"
    INFO = f"{ConsoleColors.CYAN}ℹ️{ConsoleColors.RESET}"
    PROCESSING = f"{ConsoleColors.MAGENTA}⚙️{ConsoleColors.RESET}"
    SEARCH = f"{ConsoleColors.BLUE}🔍{ConsoleColors.RESET}"
    FOLDER = f"{ConsoleColors.YELLOW}📁{ConsoleColors.RESET}"
    LOCK = f"{ConsoleColors.GREEN}🔒{ConsoleColors.RESET}"
    REPORT = f"{ConsoleColors.CYAN}📊{ConsoleColors.RESET}"
    DNS = f"{ConsoleColors.BLUE}🌐{ConsoleColors.RESET}"
    ANOMALY = f"{ConsoleColors.RED}⚠️{ConsoleColors.RESET}"
    EVIDENCE = f"{ConsoleColors.WHITE}🆔{ConsoleColors.RESET}"
    FILE = f"{ConsoleColors.DIM}📄{ConsoleColors.RESET}"
    
    @classmethod
    def get_icon_by_type(cls, file_type: str) -> str:
        """Връща икона според типа файл"""
        icons = {
            "ORIGINAL EML": cls.EML,
            "ANOMALIES": cls.ANOMALY,
            "DNS ANALYSIS": cls.DNS,
            "EVIDENCE ID": cls.EVIDENCE,
            "FORENSIC REPORT": cls.REPORT,
            "BATCH FORENSIC REPORT": cls.REPORT,
            "CORE JSON": cls.JSON,
            "ROUTING": cls.JSON,
            "TIMELINE": cls.JSON,
            "MANIFEST": cls.JSON,
            "JSON ARTIFACT": cls.JSON,
            "PDF REPORT": cls.PDF,
            "INDIVIDUAL REPORT": cls.REPORT,
            "COMBINED REPORT": cls.REPORT,
            "PDF PROOF": cls.PDF,
            "TEXT": cls.TXT,
            "BINARY": cls.BIN,
            "HTML": cls.HTML,
            "SIGNATURE": cls.SIG,
            "SHA256 HASH": cls.SHA256,
            "ATTACHMENT": cls.FILE,
            "ATTACHMENT (DANGEROUS)": cls.WARNING,
            "ATTACHMENT (PDF)": cls.PDF,
            "ATTACHMENT (IMAGE)": cls.FILE,
            "ATTACHMENT (OFFICE)": cls.FILE,
            "ATTACHMENT (TEXT)": cls.TXT,
        }
        return icons.get(file_type, cls.FILE)


# ============================================================================
# КОНСТАНТИ ЗА СТАТУС СЪОБЩЕНИЯ
# ============================================================================
STATUS_VALID = "[VALID]"
STATUS_PARTIAL = "[PARTIAL]"
STATUS_INFO = "[INFO]"
STATUS_WARNING = "[WARN]"
STATUS_ERROR = "[ERROR]"

OTS_SECTION_HEADER = "=" * 60
OTS_SUBSECTION = "-" * 40

# ============================================================================
# ЦВЕТОВА СХЕМА ЗА PDF
# ============================================================================
from hash_report_generator.pdf_object_rules import _STYLE as _CENTRAL_STYLE, unicode_font as _unicode_font, block_heading, block_data_style, display_hash, unicode_stylesheet as _unicode_stylesheet
_STATUS = _CENTRAL_STYLE['STATUS_COLORS']
COLOR_GREEN = colors.HexColor(_STATUS['ok'])
COLOR_RED = colors.HexColor(_STATUS['error'])
COLOR_ORANGE = colors.HexColor(_STATUS['warning'])
COLOR_BLUE = colors.HexColor(_STATUS['primary'])
COLOR_GREY = colors.HexColor(_STATUS['muted'])


# ============================================================================
# КЛАС ЗА НОМЕРАЦИЯ НА СТРАНИЦИ В PDF
# ============================================================================
class UnnumberedCanvas(canvas.Canvas):
    """Canvas without visible page numbers for non-report companion material."""
    pass


class NumberedCanvas(canvas.Canvas):
    """Canvas с автоматична номерация на страници само за същинския Hash Report."""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            page_num = self._pageNumber
            text = f"{page_num} / {total_pages}"
            self.setFont(_unicode_font("Helvetica"), 8)
            self.setFillColorRGB(0.5, 0.5, 0.5)
            self.drawCentredString(self._pagesize[0] / 2, 12, text)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


# ============================================================================
# КОНСТАНТИ ЗА ДИЗАЙН НА ОТЧЕТИТЕ
# ============================================================================
try:
    from .pdf_object_rules import page_geometry as _page_geometry, globalize_table as _globalize_table
except ImportError:
    from pdf_object_rules import page_geometry as _page_geometry, globalize_table as _globalize_table

_PAGE_GEOMETRY = _page_geometry()


class ReportConstants:
    """Константи за дизайн на PDF отчетите"""
    
    # --- РАЗМЕРИ НА ШРИФТОВЕ ---
    FONT_SIZE_TITLE = 16
    FONT_SIZE_HEADING = 12
    FONT_SIZE_SUBHEADING = 10
    FONT_SIZE_LEGAL = 7.3
    FONT_SIZE_SMALL = 8
    FONT_SIZE_TABLE_HEADER = 8
    FONT_SIZE_TABLE_TEXT = 7
    FONT_SIZE_TABLE_HASH = 6.5
    FONT_SIZE_EXPLANATORY_CELL = 7
    FONT_SIZE_EXPLANATORY_SMALL = 8
    FONT_SIZE_LEGAL_DECLARATION = 8
    FONT_SIZE_OTS_HEADER = 7
    FONT_SIZE_OTS_DETAIL = 7
    FONT_SIZE_PAGE_NUMBER = 8
    
    # --- МЕЖДУРЕДИЯ (LEADING) ---
    LEADING_HEADING = 16
    LEADING_SUBHEADING = 14
    LEADING_SMALL = 10
    LEADING_TABLE_TEXT = 9
    LEADING_TABLE_HASH = 8
    LEADING_EXPLANATORY_HEADER = 10
    LEADING_EXPLANATORY_CELL = 9
    LEADING_EXPLANATORY_SMALL = 10
    LEADING_LEGAL = 9
    LEADING_LEGAL_DECLARATION = 10
    LEADING_OTS_DETAIL = 9
    
    # --- ОТСТЪПИ (PADDING) ЗА ТАБЛИЦИ ---
    TABLE_PADDING = 4
    TABLE_HEADER_BOTTOM_PADDING = 6
    EXPLANATORY_TABLE_PADDING = 3
    OTS_TABLE_PADDING = 3
    
    # --- РАЗМЕРИ НА ТАБЛИЦИ (185mm) ---
    TABLE_WIDTH_MM = 170.0
    
    # --- ПРОПОРЦИИ НА КОЛОНИТЕ ЗА КОМБИНИРАН ОТЧЕТ (7 КОЛОНИ) ---
    COMBINED_TABLE_COL_PROPORTIONS_7 = {
        'number': 0.055,  # Reserve enough space for multi-digit row indices
        'name': 0.255,
        'type': 0.105,
        'size': 0.085,
        'created': 0.14,
        'modified': 0.14,
        'hash': 0.22,
    }

    INFO_TABLE_COL_PROPORTIONS = {
        'property': 0.30, 'value': 0.70
    }
    
    LEGAL_TABLE_COL_PROPORTIONS = {
        'law': 0.32, 'meaning': 0.68
    }
    
    TECH_TABLE_COL_PROPORTIONS = {
        'element': 0.28, 'meaning': 0.72
    }
    
    SUMMARY_TABLE_COL_PROPORTIONS = {
        'proof': 0.30, 'check': 0.35, 'legal': 0.35
    }
    
    CERT_TABLE_COL_PROPORTIONS = {
        'property': 0.30, 'value': 0.70
    }

    # v2.34: fixed label/value widths for visually aligned technical points.
    TIMESTAMP_TABLE_COL_PROPORTIONS = {
        'label': 0.31, 'value': 0.69
    }
    
    OTS_TABLE_COL_PROPORTIONS = {
        'file': 0.26, 'size': 0.08, 'type': 0.10, 'modified': 0.22, 'details': 0.34
    }
    
    # --- МАРЖИНИ НА СТРАНИЦИ ---
    PAGE_MARGIN_LEFT = _PAGE_GEOMETRY['left_margin_pt']
    PAGE_MARGIN_RIGHT = _PAGE_GEOMETRY['right_margin_pt']
    PAGE_MARGIN_TOP = _PAGE_GEOMETRY['top_margin_pt']
    PAGE_MARGIN_BOTTOM = _PAGE_GEOMETRY['bottom_margin_pt']
    
    # --- РАЗСТОЯНИЯ (SPACERS) ---
    SPACER_TITLE = 10
    SPACER_LEGAL = 10
    SPACER_SECTION = 5
    SPACER_HEADING = 6
    SPACER_SUBHEADING = 10
    SPACER_TABLE = 3
    SPACER_AFTER_TABLE = 20
    SPACER_AFTER_DECLARATION = 15
    SPACER_PARAGRAPH = 8
    SPACER_TIGHT = 4
    SPACER_MICRO = 2
    SPACER_OTS = 5
    SPACER_OTS_SECTION = 10
    SPACER_INFO = 15
    SPACER_BEFORE_TABLE = 20
    
    # --- ТАБЛИЦИТЕ СЕ СТИЛИЗИРАТ САМО ОТ style/30_tables.js ---


def _core_style_snapshot():
    """Load the shared presentation rules once for a style-factory operation."""
    from hash_report_generator import style_loader
    return style_loader.load_styles()


def _core_metric(name):
    """Return a named metric from the canonical style snapshot."""
    from hash_report_generator.pdf_object_rules import _STYLE
    return _STYLE["CORE_REPORT_METRICS"][name]


def _core_paragraph_color(role):
    """Resolve a paragraph role's declared text color."""
    from reportlab.lib.colors import toColor
    return toColor(_core_style_snapshot()["CORE_PARAGRAPH_PRESENTATION"][role]["text_color"])


def _core_paragraph_behavior(role, key):
    """Resolve a declared paragraph behavior and fail on unknown rules."""
    return _core_style_snapshot()["CORE_PARAGRAPH_BEHAVIOR"][role][key]


_CORE_STYLE_METRICS = {
    "title_style": ("FONT_SIZE_TITLE", None),
    "legal_style": ("FONT_SIZE_LEGAL", "LEADING_LEGAL"),
    "small_style": ("FONT_SIZE_SMALL", None),
    "warning_style": ("FONT_SIZE_SMALL", None),
    "success_style": ("FONT_SIZE_SMALL", None),
    "table_text_style": ("FONT_SIZE_TABLE_TEXT", "LEADING_TABLE_TEXT"),
    "hash_style": ("FONT_SIZE_TABLE_HASH", "LEADING_TABLE_HASH"),
    "header_style": ("FONT_SIZE_TABLE_HEADER", None),
    "legal_declaration_style": ("FONT_SIZE_LEGAL_DECLARATION", "LEADING_LEGAL_DECLARATION"),
    "timestamp_style": ("FONT_SIZE_SMALL", "LEADING_SMALL"),
    "explanatory_small_style": ("FONT_SIZE_EXPLANATORY_SMALL", "LEADING_EXPLANATORY_SMALL"),
    "explanatory_heading_style": ("FONT_SIZE_HEADING", "LEADING_HEADING"),
    "explanatory_subheading_style": ("FONT_SIZE_SUBHEADING", "LEADING_SUBHEADING"),
    "explanatory_table_header_style": ("FONT_SIZE_TABLE_HEADER", "LEADING_EXPLANATORY_HEADER"),
    "explanatory_table_cell_style": ("FONT_SIZE_EXPLANATORY_CELL", "LEADING_EXPLANATORY_CELL"),
}


def _factory_layout(role, rules):
    """Build ReportLab paragraph attributes from a single validated rule set."""
    metric_keys = _CORE_STYLE_METRICS[role]
    metrics = rules["CORE_REPORT_METRICS"]
    presentation = rules["CORE_PARAGRAPH_PRESENTATION"][role]
    layout = rules["CORE_PARAGRAPH_LAYOUT"].get(role, {})
    result = {
        "fontSize": metrics[metric_keys[0]],
        "textColor": colors.HexColor(presentation["text_color"]),
    }
    if metric_keys[1] is not None:
        result["leading"] = metrics[metric_keys[1]]
    attribute_names = {
        "space_after": "spaceAfter",
        "space_before": "spaceBefore",
        "alignment": "alignment",
        "font_name": "fontName",
    }
    for key, value in layout.items():
        result[attribute_names[key]] = _unicode_font(value) if key == "font_name" else value
    for key, value in rules["CORE_PARAGRAPH_BEHAVIOR"].get(role, {}).items():
        if key == "word_wrap":
            result["wordWrap"] = value
        else:
            raise KeyError(f"Unsupported paragraph behavior: {role}.{key}")
    return result


# ============================================================================
# ДИАГНОСТИКА НА ЧЕТЕНЕТО (cloud placeholders, заключени файлове, дълги пътища)
# ============================================================================
REPARSE_POINT = 0x400
OFFLINE_ATTRIBUTE = 0x1000
RECALL_ON_OPEN = 0x40000
RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_ATTRIBUTES = REPARSE_POINT | OFFLINE_ATTRIBUTE | RECALL_ON_OPEN | RECALL_ON_DATA_ACCESS
_TRANSIENT_OPEN_ERRNOS = (13, 32, 33)


def file_attributes(file_path) -> int:
    """Win32 file attributes, or 0 where the platform does not expose them."""
    try:
        return int(getattr(Path(file_path).stat(), 'st_file_attributes', 0) or 0)
    except (OSError, AttributeError):
        return 0


def describe_read_error(file_path, exc) -> Dict[str, object]:
    """Explain why an evidence file could not be read, in actionable terms.

    A raw ``[Errno 22] Invalid argument`` is not diagnosable by the operator.
    Cloud placeholders (OneDrive Files On-Demand), junctions, files held open by
    another process and over-long paths all surface as different errors and need
    different remedies.
    """
    errno_value = getattr(exc, 'errno', None)
    winerror = getattr(exc, 'winerror', None)
    attributes = file_attributes(file_path)
    path_text = str(file_path)
    if attributes & _CLOUD_ATTRIBUTES:
        reason = 'cloud/offline placeholder or reparse point (OneDrive Files On-Demand, junction)'
        remedy = ('download the file locally ("Always keep on this device") '
                  'or exclude it from the evidence folder')
    elif errno_value == 13 or winerror == 5:
        reason = 'access denied'
        remedy = 'the account running ChronoSeal has no read permission for this file'
    elif errno_value in (32, 33):
        reason = 'file is in use by another process'
        remedy = 'close the application that holds the file, then rerun'
    elif errno_value in (2, 3):
        reason = 'file disappeared after it was discovered'
        remedy = 'the folder changed during the scan; rerun the report'
    elif errno_value == 36 or (winerror in (206,) and len(path_text) > 259):
        reason = 'path exceeds the Windows path limit'
        remedy = 'enable LongPathsEnabled or shorten the folder path'
    elif errno_value == 22:
        reason = 'the storage or cloud provider rejected the read (invalid parameter)'
        remedy = ('the file is a cloud placeholder, a junction, or served by a filter driver '
                  'that refuses this read; copy it to a local disk first')
    else:
        reason = 'file is unreadable'
        remedy = 'check permissions, file locking and whether the file is a cloud placeholder'
    return {'reason': reason, 'remedy': remedy, 'errno': errno_value,
            'winerror': winerror, 'file_attributes': attributes}


# ============================================================================
# БАЗОВ КЛАС ЗА ГЕНЕРИРАНЕ НА ХЕШ ОТЧЕТИ
# ============================================================================
class HashGeneratorCore:
    """
    Споделено ядро за генериране на SHA-256 хеш отчети.
    Съдържа общи методи за криптография, системна информация и PDF строителни блокове.
    """
    
    def __init__(self, logger, include_ots=True):
        """
        Инициализира споделеното ядро.
        
        Args:
            logger: Logger инстанция
            include_ots: Дали да включва OTS информация
        """
        self.logger = logger
        self.include_ots = include_ots
        self.system_info = self._get_system_info()
        self.user_info = self._get_user_info()
        self.table_width = ReportConstants.TABLE_WIDTH_MM * mm
        self.constants = ReportConstants()
        self._rfc3161_token_base64 = None  # backwards-compatible last token
        self._rfc3161_tokens = {}          # START/END complete TimeStampToken Base64 values
        self._rfc3161_token_sha256 = {}    # START/END token SHA-256 values
        self._rfc3161_responses = {}       # START/END original RFC 3161 TimeStampResp DER bytes
        self._rfc3161_response_sha256 = {} # START/END TimeStampResp SHA-256 values
        self._rfc3161_response_size = {}   # START/END TimeStampResp sizes in bytes
        self._rfc3161_validation = {}      # START/END signer/chain/CRL/OCSP validation details
        self._rfc3161_validation_artifacts = {}  # START/END cert/CRL/OCSP binary artifacts
        self._last_tsa_error = None
        self._last_tsa_attempts = []       # ordered TSA attempts for the latest marker
        self._tsa_attempts_by_marker = {}  # START/END complete attempt history for SQLite persistence
        self._last_tsa_endpoint = None     # selected successful endpoint, if any
        self._tsa_last_request_perf = {}   # provider-specific request throttling
    
    # ========================================================================
    # СИСТЕМНА ИНФОРМАЦИЯ
    # ========================================================================
    def _get_system_info(self) -> Dict:
        """Взема системна информация"""
        try:
            return {
                "computer_name": socket.gethostname(),
                "os": platform.system(),
                "os_version": platform.release(),
                "hardware_id": str(uuid.getnode())
            }
        except:
            return {"computer_name": "Unknown", "os": "Unknown", "hardware_id": "Unknown"}
    
    def _get_user_info(self) -> Dict:
        """Взема потребителска информация"""
        try:
            return {"username": getpass.getuser()}
        except:
            return {"username": "Unknown"}
    
    def _get_current_time(self):
        """Взема текущо време в CET/CEST"""
        if PYTZ_AVAILABLE:
            now = datetime.now(pytz.timezone('Europe/Berlin'))
            timezone_str = "CET/CEST"
        else:
            now = datetime.now()
            timezone_str = "Local"
        return now, timezone_str

    def _create_report_identity(self) -> Dict[str, object]:
        """Create one immutable identity used by both the PDF body and filename.

        Filename format (Windows-safe):
          YYYY-MM-DD-HHMMSSmmm_-_REPORTID-HASHREPORT.pdf

        The millisecond timestamp is created once.  A short UUID component in the
        Report ID prevents collisions even when two reports start in the same ms.
        """
        now, timezone_str = self._get_current_time()
        milliseconds = f"{now.microsecond // 1000:03d}"
        filename_timestamp = now.strftime('%Y-%m-%d-%H%M%S') + milliseconds
        report_id = (
            f"RPT-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}{milliseconds}-"
            f"{uuid.uuid4().hex[:8].upper()}"
        )
        # The concrete generator sets the report type before output.
        filename = f"{report_id}_HASHREPORT.pdf"
        return {
            'now': now,
            'timezone_str': timezone_str,
            'report_id': report_id,
            'filename_timestamp': filename_timestamp,
            'filename': filename,
        }

    @staticmethod
    def _is_generated_hash_report(file_path: Path) -> bool:
        """Return True only for reports generated by this package.

        This prevents a new folder report from recursively hashing older generated
        reports while preserving unrelated PDF evidence.
        """
        name = file_path.name
        modern = re.fullmatch(
            r'(?:\d{4}-\d{2}-\d{2}-\d{9}_-_)?RPT-\d{8}-\d{9}-[0-9A-Fa-f]{8}(?:-HASHREPORT|_HASHREPORT_TYP_(?:COMBO|SINGLE))\.pdf',
            name,
            flags=re.IGNORECASE,
        )
        legacy = re.search(r'_hash_report_(?:combined|individual)\.pdf$', name, re.IGNORECASE)
        explanatory = re.search(r'_-_ERLAEUTERUNG\.pdf$', name, re.IGNORECASE)
        # Our own discovery audit must never become evidence of itself.
        discovery_audit = name.lower() == 'discovery-unreadable.json'
        evidence_db = name.lower() in {
            'hash_report_evidence.sqlite3',
            'hash_report_evidence.sqlite3-shm',
            'hash_report_evidence.sqlite3-wal',
            'hash_report_evidence.sqlite3-journal',
        }
        return bool(modern or legacy or explanatory or evidence_db or discovery_audit)

    @staticmethod
    def _get_file_times(file_path: Path) -> Tuple[datetime, datetime]:
        """Return creation/birth metadata and last modification time."""
        return HashGeneratorCore._times_from_stat(file_path.stat())

    @staticmethod
    def _times_from_stat(stat) -> Tuple[datetime, datetime]:
        """Return creation/birth and modification times from one stat snapshot."""
        if hasattr(stat, 'st_birthtime'):
            created_ts = stat.st_birthtime
        elif os.name == 'nt':
            created_ts = stat.st_ctime
        else:
            created_ts = stat.st_ctime
        return datetime.fromtimestamp(created_ts), datetime.fromtimestamp(stat.st_mtime)
    
    # ========================================================================
    # КРИПТОГРАФСКИ ФУНКЦИИ
    # ========================================================================
    def calculate_sha256(self, file_path: Path) -> str:
        """Изчислява SHA-256 хеш на файл.

        Грешка при четене или промяна на файла по време на хеширането се
        вдига като изключение; никога не се връща стойност, наподобяваща хеш.
        """
        attempts = 3
        for attempt in range(attempts):
            sha256_hash = hashlib.sha256()
            try:
                with open(file_path, "rb") as f:
                    before = os.fstat(f.fileno())
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256_hash.update(chunk)
                    after = os.fstat(f.fileno())
                break
            except OSError as e:
                # A live evidence folder (SQLite -wal/-shm, logs) is briefly
                # locked by its owner; one short retry avoids a spurious failure.
                if (getattr(e, 'errno', None) in _TRANSIENT_OPEN_ERRNOS
                        and attempt + 1 < attempts):
                    time.sleep(0.2 * (attempt + 1))
                    continue
                info = describe_read_error(file_path, e)
                self.logger.error(f"Error calculating hash for {file_path}: {e} "
                                  f"[{info['reason']}; errno={info['errno']}; winerror={info['winerror']}]")
                raise
            except Exception as e:
                self.logger.error(f"Error calculating hash for {file_path}: {e}")
                raise
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            msg = f"File changed while hashing: {file_path}"
            self.logger.error(msg)
            raise RuntimeError(msg)
        return sha256_hash.hexdigest()

    @staticmethod
    def _aggregate_checksum_payload(files_info: List[Dict]) -> bytes:
        """Return the exact legacy aggregate byte stream used by Total Checksum.

        Compatibility rule (v2.20+): for every report entry, concatenate the
        hexadecimal SHA-256 digest and the displayed/relative file name, in the
        same deterministic order as ``files_info``, then UTF-8 encode the result.

        All Total Checksum algorithms in v2.34 are calculated over THIS SAME
        payload. Therefore the SHA-256 Total Checksum remains backward-compatible
        with reports produced by earlier versions.
        """
        combined = "".join(f"{f['hash']}{f['name']}" for f in files_info)
        return combined.encode("utf-8")

    def _generate_checksum(self, files_info: List[Dict]) -> str:
        """Generate the legacy/backward-compatible SHA-256 Total Checksum."""
        return hashlib.sha256(self._aggregate_checksum_payload(files_info)).hexdigest()

    @staticmethod
    def _crc64_xz(data: bytes) -> int:
        """CRC-64/XZ used by XZ Utils and 7-Zip (reflected ECMA polynomial)."""
        poly = 0xC96C5795D7870F42
        crc = 0xFFFFFFFFFFFFFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (poly if (crc & 1) else 0)
        return crc ^ 0xFFFFFFFFFFFFFFFF

    @staticmethod
    def _xxh64(data: bytes, seed: int = 0) -> int:
        """Pure-Python XXH64 implementation (seed 0), no external package needed."""
        mask = 0xFFFFFFFFFFFFFFFF
        p1 = 11400714785074694791
        p2 = 14029467366897019727
        p3 = 1609587929392839161
        p4 = 9650029242287828579
        p5 = 2870177450012600261

        def rol64(x, r):
            return ((x << r) | (x >> (64 - r))) & mask

        def read64(buf, pos):
            return int.from_bytes(buf[pos:pos + 8], "little")

        def read32(buf, pos):
            return int.from_bytes(buf[pos:pos + 4], "little")

        def round64(acc, lane):
            acc = (acc + lane * p2) & mask
            acc = rol64(acc, 31)
            return (acc * p1) & mask

        def merge_round(acc, val):
            val = round64(0, val)
            acc ^= val
            return (acc * p1 + p4) & mask

        length = len(data)
        pos = 0
        if length >= 32:
            v1 = (seed + p1 + p2) & mask
            v2 = (seed + p2) & mask
            v3 = seed & mask
            v4 = (seed - p1) & mask
            limit = length - 32
            while pos <= limit:
                v1 = round64(v1, read64(data, pos)); pos += 8
                v2 = round64(v2, read64(data, pos)); pos += 8
                v3 = round64(v3, read64(data, pos)); pos += 8
                v4 = round64(v4, read64(data, pos)); pos += 8
            h64 = (rol64(v1, 1) + rol64(v2, 7) + rol64(v3, 12) + rol64(v4, 18)) & mask
            h64 = merge_round(h64, v1)
            h64 = merge_round(h64, v2)
            h64 = merge_round(h64, v3)
            h64 = merge_round(h64, v4)
        else:
            h64 = (seed + p5) & mask

        h64 = (h64 + length) & mask
        while pos + 8 <= length:
            k1 = round64(0, read64(data, pos))
            h64 ^= k1
            h64 = (rol64(h64, 27) * p1 + p4) & mask
            pos += 8
        if pos + 4 <= length:
            h64 ^= (read32(data, pos) * p1) & mask
            h64 = (rol64(h64, 23) * p2 + p3) & mask
            pos += 4
        while pos < length:
            h64 ^= (data[pos] * p5) & mask
            h64 = (rol64(h64, 11) * p1) & mask
            pos += 1

        h64 ^= h64 >> 33
        h64 = (h64 * p2) & mask
        h64 ^= h64 >> 29
        h64 = (h64 * p3) & mask
        h64 ^= h64 >> 32
        return h64 & mask

    @staticmethod
    def _blake2sp(data: bytes) -> str:
        """BLAKE2sp-256 using hashlib's BLAKE2s tree parameters.

        BLAKE2sp stripes 64-byte BLAKE2s blocks over eight leaf nodes and hashes
        the eight 32-byte leaf digests with a root node.
        """
        parallelism = 8
        block_size = 64
        inner_size = 32

        leaves = [
            hashlib.blake2s(
                digest_size=32,
                fanout=parallelism,
                depth=2,
                leaf_size=0,
                node_offset=i,
                node_depth=0,
                inner_size=inner_size,
                last_node=(i == parallelism - 1),
            )
            for i in range(parallelism)
        ]

        for block_index, start in enumerate(range(0, len(data), block_size)):
            leaves[block_index % parallelism].update(data[start:start + block_size])

        root = hashlib.blake2s(
            digest_size=32,
            fanout=parallelism,
            depth=2,
            leaf_size=0,
            node_offset=0,
            node_depth=1,
            inner_size=inner_size,
            last_node=True,
        )
        for leaf in leaves:
            root.update(leaf.digest())
        return root.hexdigest()

    @staticmethod
    def _court_hashes(data: bytes) -> Dict[str, str]:
        """Exactly eleven evidence hashes; never substitute missing algorithms."""
        algorithms = (
            ("MD5", "md5"), ("SHA-1", "sha1"), ("SHA-224", "sha224"),
            ("SHA-256", "sha256"), ("SHA-384", "sha384"),
            ("SHA-512", "sha512"), ("SHA3-224", "sha3_224"),
            ("SHA3-256", "sha3_256"), ("SHA3-384", "sha3_384"),
            ("SHA3-512", "sha3_512"), ("RIPEMD-160", "ripemd160"),
        )
        output = {}
        for label, algorithm in algorithms:
            try:
                digest = hashlib.new(algorithm)
            except (ValueError, RuntimeError) as exc:
                raise RuntimeError(
                    f"Required hash algorithm unavailable: {label}; report blocked"
                ) from exc
            digest.update(data)
            output[label] = digest.hexdigest()
        return output

    @classmethod
    def _court_file_hashes(cls, file_path: Union[str, Path]) -> Dict[str, str]:
        """Stream file contents to avoid loading evidence into RAM."""
        names = ("md5", "sha1", "sha224", "sha256", "sha384", "sha512",
                 "sha3_224", "sha3_256", "sha3_384", "sha3_512", "ripemd160")
        labels = ("MD5", "SHA-1", "SHA-224", "SHA-256", "SHA-384", "SHA-512",
                  "SHA3-224", "SHA3-256", "SHA3-384", "SHA3-512", "RIPEMD-160")
        try:
            digests = [hashlib.new(name) for name in names]
        except (ValueError, RuntimeError) as exc:
            raise RuntimeError("Required evidence hash algorithm unavailable; report blocked") from exc
        with open(file_path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                for digest in digests:
                    digest.update(chunk)
        return {label: digest.hexdigest() for label, digest in zip(labels, digests)}

    def _generate_total_checksums(self, files_info: List[Dict]) -> Dict[str, str]:
        """Generate the complete multi-algorithm checksum set for the evidence set.

        The digest basis is intentionally identical for every algorithm and is
        identical to the historical SHA-256 Total Checksum input. CRC64 is the
        CRC-64/XZ variant used by XZ/7-Zip; XXH64 uses seed 0.
        """
        data = self._aggregate_checksum_payload(files_info)
        return {
            "CRC32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
            "CRC64": f"{self._crc64_xz(data):016x}",
            "SHA256": hashlib.sha256(data).hexdigest(),
            "SHA1": hashlib.sha1(data).hexdigest(),
            "BLAKE2sp": self._blake2sp(data),
            "MD5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            "XXH64": f"{self._xxh64(data):016x}",
            "SHA384": hashlib.sha384(data).hexdigest(),
            "SHA512": hashlib.sha512(data).hexdigest(),
            "SHA3-256": hashlib.sha3_256(data).hexdigest(),
        }
    
    @staticmethod
    def _der_length(length: int) -> bytes:
        if length < 0x80:
            return bytes([length])
        raw = length.to_bytes((length.bit_length() + 7) // 8, 'big')
        return bytes([0x80 | len(raw)]) + raw

    @classmethod
    def _der_tlv(cls, tag: int, value: bytes) -> bytes:
        return bytes([tag]) + cls._der_length(len(value)) + value

    @classmethod
    def _der_sequence(cls, *parts: bytes) -> bytes:
        return cls._der_tlv(0x30, b''.join(parts))

    @classmethod
    def _der_integer(cls, value: int) -> bytes:
        raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), 'big')
        if raw[0] & 0x80:
            raw = b'\x00' + raw
        return cls._der_tlv(0x02, raw)

    @classmethod
    def _build_rfc3161_request(cls, message_imprint: bytes, nonce: int) -> bytes:
        """Build a minimal RFC 3161 TimeStampReq for a SHA-256 imprint."""
        sha256_oid = bytes.fromhex('608648016503040201')
        alg_id = cls._der_sequence(cls._der_tlv(0x06, sha256_oid), cls._der_tlv(0x05, b''))
        imprint = cls._der_sequence(alg_id, cls._der_tlv(0x04, message_imprint))
        return cls._der_sequence(cls._der_integer(1), imprint, cls._der_integer(nonce), cls._der_tlv(0x01, b'\xff'))

    @staticmethod
    def _parse_openssl_ts_text(text: str) -> Dict[str, str]:
        """Parse the security-relevant fields printed by ``openssl ts -reply -text``."""
        fields: Dict[str, str] = {}
        patterns = {
            'status': r'^\s*Status:\s*(.+)$',
            'status_string': r'^\s*Status description:\s*(.+)$',
            'failure_info': r'^\s*Failure info:\s*(.+)$',
            'policy_oid': r'^\s*Policy OID:\s*(.+)$',
            'hash_algorithm': r'^\s*Hash Algorithm:\s*(.+)$',
            'serial_number': r'^\s*Serial number:\s*(.+)$',
            'gen_time': r'^\s*Time stamp:\s*(.+)$',
            'nonce': r'^\s*Nonce:\s*(.+)$',
            'signer': r'^\s*TSA:\s*(.+)$',
            'signature_algorithm': r'^\s*Signature Algorithm:\s*(.+)$',
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
            if m:
                fields[key] = m.group(1).strip()

        # OpenSSL prints the imprint as a small hex dump after "Message data:".
        # Parse only the hexadecimal byte area; never trust a value copied from
        # the request when describing the returned TSA token.
        m = re.search(r'^\s*Message data:\s*$([\s\S]*?)(?=^\s*[A-Za-z][A-Za-z ]*:\s*)',
                      text, re.MULTILINE | re.IGNORECASE)
        if m:
            octets = []
            for line in m.group(1).splitlines():
                hm = re.match(r'^\s*[0-9a-fA-F]{4}\s*-\s*(.*)$', line)
                if hm:
                    # Hex dump and ASCII preview are separated by 2+ spaces.
                    hex_area = re.split(r'\s{2,}', hm.group(1), maxsplit=1)[0]
                    octets.extend(re.findall(r'(?<![0-9a-fA-F])[0-9a-fA-F]{2}(?![0-9a-fA-F])', hex_area.replace('-', ' ')))
            if octets:
                fields['message_imprint'] = ''.join(octets).lower()
        return fields

    @staticmethod
    def _parse_openssl_integer(value: str) -> Optional[int]:
        if not value:
            return None
        value = value.strip()
        try:
            return int(value, 0)
        except ValueError:
            try:
                return int(value, 16)
            except ValueError:
                return None

    @staticmethod
    def _find_openssl() -> Optional[str]:
        """Locate OpenSSL on PATH and in common Windows installations."""
        found = shutil.which('openssl')
        if found:
            return found
        candidates = [
            r'C:\Program Files\OpenSSL-Win64\bin\openssl.exe',
            r'C:\Program Files\OpenSSL-Win32\bin\openssl.exe',
            r'C:\Program Files\Git\usr\bin\openssl.exe',
            r'C:\Program Files\Git\mingw64\bin\openssl.exe',
            r'C:\Program Files (x86)\Git\usr\bin\openssl.exe',
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return None

    @staticmethod
    def _format_datetime_ms(value: datetime) -> str:
        """Format a datetime with real local millisecond precision."""
        base = value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        zone = value.tzname() if value.tzinfo else ''
        offset = value.strftime('%z') if value.tzinfo else ''
        if offset and len(offset) == 5:
            offset = offset[:3] + ':' + offset[3:]
        suffix = ' '.join(x for x in (zone, offset) if x)
        return f'{base} {suffix}'.strip()

    @staticmethod
    def _format_kb(size_bytes: int, decimals: int = 3) -> str:
        """Format a byte count exclusively as binary kilobytes for report output."""
        return f"{(int(size_bytes) / 1024.0):.{decimals}f} KB"

    @staticmethod
    def _format_datetime_plain_ms(value: datetime) -> str:
        """Format a filesystem/local datetime with millisecond precision."""
        return value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    def _get_tsa_endpoints(self) -> List[Tuple[str, str]]:
        """Return primary RFC 3161 TSA plus exactly three default alternatives.

        HASH_REPORT_TSA_URL overrides only the primary endpoint.
        HASH_REPORT_TSA_ALTERNATIVES may override the three alternatives with a
        semicolon-separated list. Duplicate URLs are removed while preserving order.
        """
        primary = os.environ.get('HASH_REPORT_TSA_URL', 'http://zeitstempel.dfn.de').strip()
        defaults = [
            ('DigiCert', 'http://timestamp.digicert.com'),
            ('GlobalSign', 'http://timestamp.globalsign.com/tsa/r45standard'),
            ('Sectigo', 'http://timestamp.sectigo.com'),
        ]
        raw_alt = os.environ.get('HASH_REPORT_TSA_ALTERNATIVES', '').strip()
        if raw_alt:
            urls = [u.strip() for u in raw_alt.split(';') if u.strip()]
            alternatives = [(f'Alternative {i}', u) for i, u in enumerate(urls[:3], 1)]
            # Preserve exactly three fallback slots by filling missing custom entries.
            for item in defaults:
                if len(alternatives) >= 3:
                    break
                if item[1] not in {u for _, u in alternatives}:
                    alternatives.append(item)
        else:
            alternatives = defaults

        endpoints = [('DFN / Primary' if primary == 'http://zeitstempel.dfn.de' else 'Primary override', primary)]
        endpoints.extend(alternatives[:3])
        deduped = []
        seen = set()
        for name, url in endpoints:
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append((name, url))
        return deduped

    def _respect_tsa_rate_limit(self, tsa_url: str) -> float:
        """Honor known public TSA usage guidance. Returns actual wait in ms."""
        if 'timestamp.sectigo.com' not in tsa_url.lower():
            return 0.0
        minimum_interval_s = 15.0
        last = self._tsa_last_request_perf.get('sectigo')
        if last is None:
            return 0.0
        elapsed_s = (time.perf_counter_ns() - last) / 1_000_000_000.0
        remaining_s = minimum_interval_s - elapsed_s
        if remaining_s > 0:
            time.sleep(remaining_s)
            return remaining_s * 1000.0
        return 0.0

    def _get_rfc3161_timestamp(self, message_imprint: Optional[str] = None,
                               force_new: bool = True,
                               marker_label: str = 'START') -> Optional[str]:
        """Obtain and validate one RFC 3161 token with automatic TSA failover.

        Order: primary TSA, then three alternatives. The first endpoint that returns
        a structurally valid token whose SHA-256 imprint and nonce match the request
        and whose CMS signature verifies is selected. TSA genTime is reproduced
        exactly as issued; local request/response timestamps use milliseconds.
        """
        _hb_phase('tsa', note=str(marker_label or 'TIMESTAMP'))
        marker = (marker_label or 'TIMESTAMP').strip().upper()
        display_marker = 'STOP' if marker == 'END' else marker
        # ChronoSeal owns the authoritative PDF DocTimeStamp/DSS stage. When this
        # generator is embedded, do not duplicate network TSA calls inside the
        # report-generation subprocess. Standalone behavior is unchanged.
        if os.environ.get('CHRONOSEAL_REPORT_ONLY') == '1':
            now,_ = self._get_current_time()
            return self._generate_chronoseal_pending_record(message_imprint, marker, now)
        self._rfc3161_token_base64 = None
        self._rfc3161_tokens[marker] = None
        self._rfc3161_token_sha256[marker] = None
        self._rfc3161_responses[marker] = None
        self._rfc3161_response_sha256[marker] = None
        self._rfc3161_response_size[marker] = None
        self._rfc3161_validation[marker] = None
        self._rfc3161_validation_artifacts[marker] = []
        self._last_tsa_error = None
        self._last_tsa_attempts = []
        self._tsa_attempts_by_marker[marker] = self._last_tsa_attempts
        self._last_tsa_endpoint = None
        endpoints = self._get_tsa_endpoints()
        first_request_local, _ = self._get_current_time()

        if not REQUESTS_AVAILABLE:
            return self._generate_local_crypto_timestamp(
                message_imprint, 'Python package "requests" is unavailable',
                ' -> '.join(url for _, url in endpoints), marker, first_request_local)
        if not message_imprint or not re.fullmatch(r'[0-9a-fA-F]{64}', message_imprint):
            return self._generate_local_crypto_timestamp(
                message_imprint, 'Invalid or missing SHA-256 message imprint',
                ' -> '.join(url for _, url in endpoints), marker, first_request_local)

        openssl = self._find_openssl()
        if not openssl:
            return self._generate_local_crypto_timestamp(
                message_imprint,
                'OpenSSL executable not found; RFC 3161 response cannot be independently parsed/validated',
                ' -> '.join(url for _, url in endpoints), marker, first_request_local)

        failures = []
        total_attempts = len(endpoints)
        for attempt_no, (tsa_name, tsa_url) in enumerate(endpoints, 1):
            request_local = None
            try:
                wait_ms = self._respect_tsa_rate_limit(tsa_url)
                request_local, _ = self._get_current_time()
                request_perf = time.perf_counter_ns()
                if 'timestamp.sectigo.com' in tsa_url.lower():
                    self._tsa_last_request_perf['sectigo'] = request_perf

                nonce_int = int.from_bytes(os.urandom(16), 'big')
                request_der = self._build_rfc3161_request(bytes.fromhex(message_imprint), nonce_int)
                response = requests.post(
                    tsa_url,
                    data=request_der,
                    headers={
                        'Content-Type': 'application/timestamp-query',
                        'Accept': 'application/timestamp-reply',
                        'User-Agent': 'HashReportGenerator/2.34 RFC3161-Client',
                    },
                    timeout=30,
                    allow_redirects=True,
                )
                response.raise_for_status()
                response_local, _ = self._get_current_time()
                response_perf = time.perf_counter_ns()
                round_trip_ms = (response_perf - request_perf) / 1_000_000.0
                if not response.content:
                    raise RuntimeError('TSA returned an empty response')

                with tempfile.TemporaryDirectory(prefix='rfc3161_') as td:
                    d = Path(td)
                    query = d / 'request.tsq'
                    reply = d / 'response.tsr'
                    token = d / 'token.der'
                    certs = d / 'certs.pem'
                    verified_content = d / 'verified-content.der'
                    query.write_bytes(request_der)
                    reply.write_bytes(response.content)

                    # TimeStampResp is DER by definition for openssl ts input.
                    # IMPORTANT: openssl ts has no -inform DER option (OpenSSL 1.1.1/3.x).
                    # Using it causes every valid TSA response to be rejected locally.
                    parsed_proc = subprocess.run(
                        [openssl, 'ts', '-reply', '-in', str(reply), '-text'],
                        capture_output=True, text=True, timeout=20)
                    ts_text = (parsed_proc.stdout or '') + (parsed_proc.stderr or '')
                    if parsed_proc.returncode != 0:
                        raise RuntimeError(f'OpenSSL could not parse TSA reply: {ts_text.strip()}')

                    parsed = self._parse_openssl_ts_text(ts_text)
                    status = parsed.get('status', '')
                    if not re.search(r'granted', status, re.IGNORECASE):
                        details = parsed.get('status_string') or parsed.get('failure_info') or 'no details'
                        raise RuntimeError(f'TSA rejected the request: {status or "Unknown status"}; {details}')

                    returned_imprint = parsed.get('message_imprint', '').lower()
                    if returned_imprint != message_imprint.lower():
                        raise RuntimeError(
                            f'TSA message imprint mismatch: requested {message_imprint.lower()}, '
                            f'returned {returned_imprint or "N/A"}')

                    hash_algorithm = parsed.get('hash_algorithm', '').lower().replace('-', '')
                    if 'sha256' not in hash_algorithm:
                        raise RuntimeError(f'Unexpected TSA hash algorithm: {parsed.get("hash_algorithm", "N/A")}')

                    returned_nonce = self._parse_openssl_integer(parsed.get('nonce', ''))
                    if returned_nonce != nonce_int:
                        raise RuntimeError(
                            f'TSA nonce mismatch: requested {nonce_int}, returned {parsed.get("nonce", "N/A")}')

                    # Extract ContentInfo/TimeStampToken from the DER TimeStampResp.
                    # -inform belongs to cms/pkcs7, not to the openssl ts command.
                    token_proc = subprocess.run(
                        [openssl, 'ts', '-reply', '-in', str(reply),
                         '-token_out', '-out', str(token)],
                        capture_output=True, text=True, timeout=20)
                    if token_proc.returncode != 0 or not token.exists() or token.stat().st_size == 0:
                        raise RuntimeError('TSA reply did not contain an extractable TimeStampToken')

                    cms_proc = subprocess.run(
                        [openssl, 'cms', '-verify', '-inform', 'DER', '-in', str(token),
                         '-noverify', '-out', str(verified_content)],
                        capture_output=True, text=True, timeout=20)
                    if cms_proc.returncode != 0:
                        cms_error = ((cms_proc.stderr or '') + (cms_proc.stdout or '')).strip()
                        raise RuntimeError(f'CMS signature verification failed: {cms_error}')

                    token_der = token.read_bytes()
                    token_b64 = base64.b64encode(token_der).decode('ascii')
                    token_sha256 = hashlib.sha256(token_der).hexdigest()
                    self._rfc3161_token_base64 = token_b64
                    self._rfc3161_tokens[marker] = token_b64
                    self._rfc3161_token_sha256[marker] = token_sha256
                    response_der = bytes(response.content)
                    response_sha256 = hashlib.sha256(response_der).hexdigest()
                    self._rfc3161_responses[marker] = response_der
                    self._rfc3161_response_sha256[marker] = response_sha256
                    self._rfc3161_response_size[marker] = len(response_der)
                    self._last_tsa_endpoint = tsa_url

                    # v2.34: identify the actual CMS SignerInfo certificate, then validate
                    # timestamping EKU, certificate chain, trust anchor, CRL and OCSP.
                    # A validation-network failure is reported as UNAVAILABLE; it is never
                    # silently converted to GOOD/PASS.
                    validation = None
                    validation_error = None
                    if RFC3161_VALIDATION_AVAILABLE:
                        try:
                            validation = validate_rfc3161_token(
                                token_der=token_der,
                                marker=marker,
                                openssl_path=openssl,
                                gen_time_text=parsed.get('gen_time', ''),
                            )
                            self._rfc3161_validation[marker] = validation
                            self._rfc3161_validation_artifacts[marker] = list(validation.get('artifacts') or [])
                            if validation.get('chain', {}).get('status') == 'FAILED':
                                raise RuntimeError(
                                    'TSA signer certificate chain validation failed: '
                                    + str(validation.get('chain', {}).get('detail', 'unknown reason'))
                                )
                            if validation.get('crl', {}).get('status') == 'REVOKED':
                                raise RuntimeError('TSA signer certificate is REVOKED according to the validated CRL')
                            if validation.get('ocsp', {}).get('status') == 'REVOKED':
                                raise RuntimeError('TSA signer certificate is REVOKED according to the validated OCSP response')
                        except Exception as exc:
                            validation_error = str(exc).replace('\n', ' ').strip()
                            if 'REVOKED' in validation_error.upper():
                                raise
                            self._rfc3161_validation[marker] = {
                                'marker': marker, 'error': validation_error, 'lines': [], 'artifacts': []
                            }
                            self._rfc3161_validation_artifacts[marker] = []

                    prior_failures = [a for a in self._last_tsa_attempts if a.get('status') == 'FAILED']
                    self._last_tsa_attempts.append({
                        'attempt': attempt_no, 'name': tsa_name, 'url': tsa_url,
                        'status': 'SUCCESS', 'duration_ms': round_trip_ms,
                    })
                    lines = [
                        f'RFC 3161 TIMESTAMP TOKEN - {marker}',
                        '  • Protocol: RFC 3161',
                        f'  • Marker: {marker}',
                        f'  • Selected TSA: {tsa_name}',
                        f'  • TSA Endpoint: {tsa_url}',
                        f'  • Failover Position: {attempt_no}/{total_attempts}',
                        f'  • Local Request Start: {self._format_datetime_ms(request_local)}',
                        f'  • Local Response Received: {self._format_datetime_ms(response_local)}',
                        f'  • TSA Round-Trip Duration: {round_trip_ms:.3f} ms',
                    ]
                    if wait_ms > 0:
                        lines.append(f'  • Provider Rate-Limit Wait: {wait_ms:.3f} ms')
                    if prior_failures:
                        lines.append('  • Earlier TSA Attempts:')
                        for item in prior_failures:
                            lines.append(
                                f"      - {item['attempt']}/{total_attempts} {item['name']} "
                                f"({item['url']}): FAILED - {item['error']}")
                    lines += [
                        f"  • Status: {parsed.get('status', 'Unknown')}",
                        f"  • Status Description: {parsed.get('status_string', 'N/A')}",
                        f"  • Hash Algorithm: {parsed.get('hash_algorithm', 'SHA-256')}",
                        f'  • Message Imprint (returned and verified): {returned_imprint}',
                        f"  • Timestamp (genTime, exactly as issued by TSA): {parsed.get('gen_time', 'N/A')}",
                        '  • TSA genTime Precision: preserved exactly; fractional milliseconds are shown only if the TSA signed them.',
                        f"  • TSA Serial Number: {parsed.get('serial_number', 'N/A')}",
                        f"  • TSA Policy OID: {parsed.get('policy_oid', 'N/A')}",
                        f"  • Nonce (returned and verified): {parsed.get('nonce', 'N/A')}",
                        '  • Certificate Requested: Yes',
                        '  • Token Format: CMS / SignedData',
                        f"  • Signer / TSA: {parsed.get('signer', 'N/A')}",
                        f"  • Signature Algorithm: {parsed.get('signature_algorithm', 'N/A')}",
                        f'  • TimeStampToken SHA-256: {token_sha256}',
                        f'  • Embedded RFC 3161 Response File: RFC3161_{display_marker}.tsr',
                        '  • Embedded Response Format: RFC 3161 TimeStampResp / DER',
                        f'  • Embedded Response Size: {self._format_kb(len(response_der))}',
                        f'  • Embedded Response SHA-256: {response_sha256}',
                        '  • Query Binding Verification: PASS (SHA-256 imprint + nonce)',
                        '  • CMS Signature Verification: PASS (cryptographic signature)',
                    ]
                    if validation and validation.get('lines'):
                        lines.extend(validation['lines'])
                    elif validation_error:
                        lines.append(f'  • Certificate / Revocation Validation: UNAVAILABLE ({validation_error})')
                    elif not RFC3161_VALIDATION_AVAILABLE:
                        lines.append('  • Certificate / Revocation Validation: UNAVAILABLE (validation module not installed)')
                    lines += [
                        '  • Cryptographic Binding: The returned TSA token contains the verified SHA-256 Message Imprint shown above.',
                        '  • Evidence Preservation: ChronoSeal embeds TSA certificate/revocation candidate material directly in the final PDF DSS; raw validation artifacts are preserved in the external evidence package.',
                        '  • Qualification Status: No claim of a qualified electronic time stamp is made solely from RFC 3161.',
                    ]
                    return '\n'.join(lines)

            except Exception as e:
                err = str(e).replace('\n', ' ').strip()
                self._last_tsa_error = err
                attempt = {
                    'attempt': attempt_no, 'name': tsa_name, 'url': tsa_url,
                    'status': 'FAILED', 'error': err,
                }
                self._last_tsa_attempts.append(attempt)
                failures.append(f'{attempt_no}/{total_attempts} {tsa_name} ({tsa_url}): {err}')
                if self.logger:
                    self.logger.warning(f'TSA attempt failed [{marker}] {tsa_name} ({tsa_url}): {err}')

        reason = ' | '.join(failures) if failures else 'All configured TSA endpoints failed'
        return self._generate_local_crypto_timestamp(
            message_imprint, reason,
            ' -> '.join(url for _, url in endpoints), marker, first_request_local)

    def _generate_chronoseal_pending_record(self, message_imprint: Optional[str] = None,
                                            marker_label: str = 'TIMESTAMP',
                                            request_local: Optional[datetime] = None) -> str:
        """Describe the embedded ChronoSeal hand-off without falsely reporting a TSA failure.

        The report PDF is generated before the authoritative incremental DocTimeStamp
        revisions are appended. Therefore the visible pre-seal page cannot truthfully
        contain the later token's genTime/fingerprint without modifying bytes after the
        final STOP signature. The authoritative result is the embedded PDF signature/DSS
        state and the final ChronoSeal audit produced after reopen verification.
        """
        now, _ = self._get_current_time()
        marker = (marker_label or 'TIMESTAMP').strip().upper()
        started = request_local or now
        return (
            f'RFC 3161 TIMESTAMP STATUS: CHRONOSEAL FINALIZATION - {marker}\n'
            f'  • Marker: {marker}\n'
            '  • TSA Endpoint Sequence: ChronoSeal RFC3161 orchestrator\n'
            '  • Finalization State: DocTimeStamp is appended by ChronoSeal after report-page generation\n'
            'CHRONOSEAL PRE-SEAL RECORD (INFORMATIONAL ONLY)\n'
            f'  • Local Report Stage Start: {self._format_datetime_ms(started)}\n'
            f'  • Local Report Stage Record Time: {self._format_datetime_ms(now)}\n'
            f'  • Message Imprint: {(message_imprint or "N/A").lower()}\n'
            '  • Evidentiary Status: See the embedded START/STOP DocTimeStamp signatures and final certificate audit.\n'
            '  • Verification: Validate PDF ByteRange, RFC3161 CMS token, TSA chain and DSS/Certs from the final PDF.'
        )

    def _generate_local_crypto_timestamp(self, message_imprint: Optional[str] = None,
                                         reason: Optional[str] = None,
                                         tsa_url: Optional[str] = None,
                                         marker_label: str = 'TIMESTAMP',
                                         request_local: Optional[datetime] = None) -> str:
        """Create an audit record only; never present it as timestamp evidence."""
        now, timezone_str = self._get_current_time()
        process_id = os.getpid()
        machine_id = self.system_info.get('hardware_id', 'unknown')
        record_id = uuid.uuid4().hex
        endpoint = tsa_url or os.environ.get('HASH_REPORT_TSA_URL', 'http://zeitstempel.dfn.de')
        marker = (marker_label or 'TIMESTAMP').strip().upper()
        started = request_local or now
        return (
            f'RFC 3161 TIMESTAMP STATUS: UNAVAILABLE - {marker}\n'
            f'  • Marker: {marker}\n'
            f'  • TSA Endpoint Sequence: {endpoint}\n'
            f'  • Failure Reason: {reason or "TSA request/validation failed"}\n'
            'LOCAL GENERATION RECORD (INFORMATIONAL ONLY)\n'
            f'  • Local Request Start: {self._format_datetime_ms(started)}\n'
            f'  • Local Failure/Record Time: {self._format_datetime_ms(now)}\n'
            f'  • Message Imprint: {(message_imprint or "N/A").lower()}\n'
            f'  • Record ID: {record_id}\n'
            f'  • Process ID: {process_id}\n'
            f'  • Machine ID: {machine_id}\n'
            '  • Evidentiary Status: NOT an RFC 3161 token and NOT independent time evidence.\n'
            '  • Action: Correct the TSA/OpenSSL/network problem and regenerate the report.'
        )

    def _build_end_timestamp_imprint(self, evidence_sha256: str, report_id: str,
                                    start_timestamp_text: str) -> Tuple[str, str]:
        """Create a closing digest that cryptographically links END to START.

        If START has a real token, its token SHA-256 is used.  Otherwise the
        SHA-256 of the complete START status text is used, so the closing marker
        still records exactly what START state was present without pretending
        that a failed START was a TSA token.
        """
        start_token_sha = self._rfc3161_token_sha256.get('START')
        start_anchor_type = 'START TimeStampToken SHA-256' if start_token_sha else 'START status-text SHA-256'
        start_anchor = start_token_sha or hashlib.sha256((start_timestamp_text or '').encode('utf-8')).hexdigest()
        canonical = (
            'HASH-REPORT-END-v1\n'
            f'EVIDENCE-SHA256={evidence_sha256.lower()}\n'
            f'START-ANCHOR={start_anchor.lower()}\n'
            f'REPORT-ID={report_id}\n'
        ).encode('utf-8')
        return hashlib.sha256(canonical).hexdigest(), start_anchor_type

    def _add_aligned_key_value_table(self, story, rows, styles, *, label_ratio=None, compact=True):
        """Render technical facts in a fixed two-column grid.

        v2.34 replaces visually ragged bullet paragraphs with one stable label
        column and one value column. Long hashes/URLs may wrap, but every field
        starts at exactly the same horizontal position.
        """
        if not rows:
            return
        label_ratio = label_ratio or ReportConstants.TIMESTAMP_TABLE_COL_PROPORTIONS['label']
        label_width = self.table_width * label_ratio
        value_width = self.table_width - label_width
        label_style = ParagraphStyle(
            'AlignedKVLabelV231', parent=styles['timestamp_style'],
            fontName=_unicode_font('Helvetica-Bold'), fontSize=ReportConstants.FONT_SIZE_SMALL,
            leading=ReportConstants.LEADING_SMALL, wordWrap='WORD',
            splitLongWords=1, spaceBefore=0, spaceAfter=0,
        )
        value_style = ParagraphStyle(
            'AlignedKVValueV231', parent=styles['timestamp_style'],
            fontSize=ReportConstants.FONT_SIZE_SMALL,
            leading=ReportConstants.LEADING_SMALL, wordWrap='CJK',
            splitLongWords=1, spaceBefore=0, spaceAfter=0,
        )
        data=[]
        for label, value in rows:
            value = display_hash(value)
            data.append([
                Paragraph(self._escape_reportlab_text(str(label)), label_style),
                Paragraph(self._escape_reportlab_text(str(value)), value_style),
            ])
        table = Table(data, colWidths=[label_width, value_width], hAlign='LEFT', splitByRow=1)
        block = _CENTRAL_STYLE['KEY_VALUE_BLOCK']
        pad = block['compact_padding_pt'] if compact else block['padding_pt']
        commands = [
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),pad),
            ('RIGHTPADDING',(0,0),(-1,-1),pad),
            ('TOPPADDING',(0,0),(-1,-1),block['vertical_padding_pt']),
            ('BOTTOMPADDING',(0,0),(-1,-1),block['vertical_padding_pt']),
        ]
        if len(data) > 1:
            commands.append(('LINEBELOW',(0,0),(-1,-2),block['rule_pt'],colors.HexColor(block['rule_color'])))
        for idx in range(len(data)):
            if idx % 2:
                commands.append(('BACKGROUND',(0,idx),(-1,idx),colors.HexColor(block['stripe_color'])))
        table.setStyle(TableStyle(commands))
        story.append(table)

    @staticmethod
    def _escape_reportlab_text(value: str) -> str:
        """Escape dynamic text before it is inserted into a ReportLab Paragraph."""
        return (value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    def _timestamp_text_to_rows(self, timestamp_text: str, *, signature_only: bool = False):
        """Convert RFC3161 diagnostic text to aligned label/value rows.

        ``signature_only`` removes protocol-wide facts that are shown once in the
        preceding ``Cryptographic Timestamp`` section.  START/STOP then contain
        only the data and validation result of the respective TSA signature.
        """
        heading = None
        rows = []
        continuation = []
        common_labels = {
            'Protocol', 'Marker', 'Hash Algorithm', 'Certificate Requested',
            'Token Format', 'TSA genTime Precision', 'Embedded Response Format',
            'Evidence Preservation', 'Qualification Status',
        }
        # OpenSSL's textual parser may leave these two fields unspecified even
        # though the actual SignerInfo certificate is identified below.  Do not
        # show misleading N/A/unspecified placeholders in the signature block.
        redundant_labels = {'Signer / TSA', 'Signature Algorithm'}

        for raw in (timestamp_text or '').splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith('RFC 3161 TIMESTAMP TOKEN') or line.startswith('RFC 3161 TIMESTAMP STATUS'):
                heading = line
                continue
            if line == 'LOCAL GENERATION RECORD (INFORMATIONAL ONLY)':
                rows.append(('Local record', 'INFORMATIONAL ONLY - not independent RFC 3161 time evidence'))
                continue
            line = re.sub(r'^[•-]\s*', '', line)
            if ': ' in line:
                label, value = line.split(': ', 1)
                label, value = label.strip(), value.strip()
                if label in redundant_labels:
                    continue
                if signature_only and label in common_labels:
                    continue
                rows.append((label, value))
            elif line.endswith(':'):
                label = line[:-1].strip()
                if label not in redundant_labels and not (signature_only and label in common_labels):
                    rows.append((label, ''))
            else:
                continuation.append(line)
        if continuation:
            rows.append(('Details', ' | '.join(continuation)))
        return heading, rows

    def _add_timestamp_general_section(self, story, styles, *, single_file: bool = False):
        """Render protocol-wide RFC3161 information once, before START."""
        story.append(block_heading('Cryptographic Timestamp'))
        start_binding = (
            'SHA-256 of the evidence file'
            if single_file else
            'SHA-256 Total Checksum of the evidence set'
        )
        rows = [
            ('Protocol', 'RFC 3161 / RFC 5816 Time-Stamp Protocol'),
            ('Evidence Digest Algorithm', 'SHA-256 (file/evidence-set digest; TSA token algorithm must be read from each token)'),
            ('Token Format', 'CMS / SignedData'),
            ('Timestamp Structure', 'START signature + STOP signature'),
            ('START Binding', start_binding),
            ('STOP Binding', 'SHA-256 closing digest linking the evidence SHA-256, START TimeStampToken SHA-256 and Report ID'),
            ('TSA Selection', 'Primary TSA with configured failover; the actually selected TSA is recorded separately for START and STOP'),
            ('Token Verification', 'Message Imprint + Nonce + CMS signature'),
            ('Signer Validation', 'TSA signer certificate, critical Time Stamping EKU, validity at genTime and X.509 certificate chain'),
            ('Revocation Validation', 'CRL and OCSP when available; unavailable network validation is reported explicitly'),
            ('genTime Precision', 'Preserved exactly as signed by the TSA; fractional precision is shown only when present in the token'),
            ('Evidence Preservation', 'TSA certificate/revocation candidate material is embedded directly in the final PDF DSS by ChronoSeal; raw validation artifacts are preserved in the external evidence package'),
            ('Qualification Status', 'RFC 3161 alone is not presented as proof of a qualified electronic time stamp'),
            ('Local Timing Status', 'Local request/response times and Processing Duration are informational measurements, not TSA-certified time evidence'),
        ]
        self._add_aligned_key_value_table(story, rows, styles)

    def _add_timestamp_block(self, story, styles, timestamp_text: str, *, display_marker: str = None,
                             signature_only: bool = False, show_internal_heading: bool = False):
        heading, rows = self._timestamp_text_to_rows(timestamp_text, signature_only=signature_only)
        if show_internal_heading and heading:
            if display_marker:
                heading = re.sub(r'\bEND\b', display_marker, heading)
            story.append(Paragraph(f'<b>{self._escape_reportlab_text(heading)}</b>', styles['small_style']))
            story.append(Spacer(1, ReportConstants.SPACER_MICRO))
        if rows:
            self._add_aligned_key_value_table(story, rows, styles)
        else:
            story.append(Paragraph('<i>No timestamp details available</i>', styles['warning_style']))

    def _add_end_timestamp_section(self, story, styles, end_timestamp: str,
                                   duration_ms: float, evidence_sha256: str,
                                   end_imprint: str, start_anchor_type: str):
        """Append the closing RFC 3161 signature and duration explanation."""
        story.append(block_heading('Cryptographic Timestamp STOP'))

        # Closing-link facts belong to the STOP signature itself.
        closing_rows = [
            ('Evidence-set SHA-256', evidence_sha256),
            ('STOP Closing Message Imprint', end_imprint),
            ('START Anchor Used by STOP', start_anchor_type.replace('END', 'STOP')),
        ]
        self._add_aligned_key_value_table(story, closing_rows, styles)
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))
        self._add_timestamp_block(
            story, styles, end_timestamp,
            display_marker='STOP', signature_only=True, show_internal_heading=False)

        # Processing Duration is deliberately placed AFTER the STOP signature.
        # It is a local monotonic measurement and must not be confused with a
        # TSA-signed duration or with the final PDF serialization time.
        story.append(Spacer(1, ReportConstants.SPACER_TIGHT))
        duration_rows = [
            ('Processing Duration', f'{duration_ms:.3f} ms'),
            ('Processing Duration Explanation',
             'Local elapsed time measured with a monotonic high-resolution timer from immediately before the START TSA request until completion of the STOP TSA request and validation. It includes local report preparation between both requests; it is informational, is not TSA-certified, and does not include final PDF serialization or attachment embedding.'),
        ]
        self._add_aligned_key_value_table(story, duration_rows, styles)

    def _add_rfc3161_tokens_at_document_end(self, story, styles):
        """Legacy hook retained for standalone compatibility; ChronoSeal report-only mode delegates final RFC3161/DSS embedding to the orchestrator."""
        return

    def _embed_rfc3161_responses_in_pdf(self, pdf_path: Union[str, Path]) -> List[Dict]:
        """Embed RFC 3161 responses and all captured validation artifacts.

        v2.34 preserves the original START/END TimeStampResp bytes plus the exact
        X.509 certificates, CRL and OCSP response used for validation.  Every
        attachment is re-read from the completed PDF and checked byte-for-byte
        by SHA-256 before the temporary file atomically replaces the report.
        """
        _hb_phase('embed')
        responses = getattr(self, '_rfc3161_responses', {}) or {}
        validation_artifacts = getattr(self, '_rfc3161_validation_artifacts', {}) or {}

        attachments_to_add = []
        for marker in ('START', 'END'):
            data = responses.get(marker)
            if data:
                attachments_to_add.append({
                    'marker': marker,
                    'filename': f"RFC3161_{'STOP' if marker == 'END' else marker}.tsr",
                    'data': bytes(data),
                    'kind': 'RFC3161_TIMESTAMP_RESPONSE',
                })
            for artifact in validation_artifacts.get(marker, []) or []:
                artifact_data = artifact.get('data')
                artifact_name = artifact.get('filename')
                if artifact_data and artifact_name:
                    external_name = str(artifact_name)
                    if marker == 'END' and external_name.startswith('RFC3161_END_'):
                        external_name = 'RFC3161_STOP_' + external_name[len('RFC3161_END_'):]
                    attachments_to_add.append({
                        'marker': marker,
                        'filename': external_name,
                        'data': bytes(artifact_data),
                        'kind': artifact.get('kind', 'VALIDATION_ARTIFACT'),
                    })

        if not attachments_to_add:
            return []
        if not PYPDF_AVAILABLE:
            raise RuntimeError('pypdf is required to embed RFC 3161 validation evidence')

        # Duplicate names are forbidden because a verifier must be able to address
        # one exact artifact by its printed filename.
        seen_names = {}
        unique_items = []
        for item in attachments_to_add:
            previous = seen_names.get(item['filename'])
            if previous is not None:
                if previous != item['data']:
                    raise RuntimeError(f"Duplicate embedded artifact filename: {item['filename']}")
                continue  # identical artifact shared by START and STOP is embedded once
            seen_names[item['filename']] = item['data']
            item['size'] = len(item['data'])
            item['sha256'] = hashlib.sha256(item['data']).hexdigest()
            unique_items.append(item)
        attachments_to_add = unique_items

        pdf_path = Path(pdf_path)
        tmp_path = pdf_path.with_name(pdf_path.name + '.embed.tmp')
        if tmp_path.exists():
            tmp_path.unlink()

        try:
            writer = PdfWriter(clone_from=str(pdf_path))
            for item in attachments_to_add:
                writer.add_attachment(item['filename'], item['data'])
            with open(tmp_path, 'wb') as fh:
                writer.write(fh)

            # Re-open the final candidate and verify every embedded byte sequence.
            reader = PdfReader(str(tmp_path))
            attachments = reader.attachments
            for item in attachments_to_add:
                candidates = attachments.get(item['filename'])
                if candidates is None:
                    raise RuntimeError(f"Embedded attachment missing after write: {item['filename']}")
                if isinstance(candidates, (bytes, bytearray)):
                    candidates = [bytes(candidates)]
                if not any(hashlib.sha256(bytes(blob)).hexdigest() == item['sha256'] for blob in candidates):
                    raise RuntimeError(f"Embedded attachment hash mismatch: {item['filename']}")

            os.replace(tmp_path, pdf_path)
            return [{k: v for k, v in item.items() if k != 'data'} for item in attachments_to_add]
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise


    def _save_sqlite_evidence_database(self, *, report_id: str, report_type: str,
                                       generated_at: datetime, timezone_label: str,
                                       output_pdf: Union[str, Path], files_info: List[Dict],
                                       evidence_sha256: str, start_timestamp_text: str,
                                       end_timestamp_text: str, end_message_imprint: str,
                                       start_anchor_type: str, processing_duration_ms: float,
                                       embedded_pdf_artifacts: List[Dict],
                                       explanatory_pdf: Optional[Union[str, Path]] = None,
                                       ots_info: Optional[Dict] = None) -> Optional[Dict]:
        """Persist every report fact and binary validation artifact in SQLite.

        The database is auxiliary and intentionally excluded from evidence-set
        discovery. A database failure never changes the already generated PDF; it
        is surfaced explicitly to the caller/console instead of being hidden.
        """
        _hb_phase('sqlite')
        if not EVIDENCE_DATABASE_AVAILABLE:
            if self.logger:
                self.logger.error('SQLite evidence database module is unavailable')
            return None
        try:
            output_pdf = Path(output_pdf).resolve()
            configured = os.environ.get('HASH_REPORT_DB_PATH', '').strip()
            db_path = Path(configured).expanduser().resolve() if configured else output_pdf.parent / DEFAULT_DB_FILENAME
            record = build_database_record(
                self, report_id=report_id, report_type=report_type, generated_at=generated_at,
                timezone_label=timezone_label, output_pdf=output_pdf, files_info=files_info,
                evidence_sha256=evidence_sha256, start_timestamp_text=start_timestamp_text,
                end_timestamp_text=end_timestamp_text, end_message_imprint=end_message_imprint,
                start_anchor_type=start_anchor_type, processing_duration_ms=processing_duration_ms,
                embedded_pdf_artifacts=embedded_pdf_artifacts,
                explanatory_pdf=Path(explanatory_pdf) if explanatory_pdf else None,
                ots_info=ots_info,
            )
            return save_database_record(db_path, record)
        except Exception as exc:
            if self.logger:
                self.logger.error(f'Could not persist SQLite evidence database: {exc}')
            return None


    def _verify_before_generate(self, files_info: List[Dict]) -> bool:
        """Верифицира файловете преди генериране

        v5.5.0: this pass re-hashes every discovered file and is therefore the
        longest silent phase of a run. It now reports progress so the pipeline
        watchdog can distinguish "slow" from "stalled".
        """
        if not files_info:
            if self.logger:
                self.logger.error("No files to generate report")
            return False
        _hb_phase('verify', total=len(files_info))
        for file_info in files_info:
            _hb_tick()
            file_path = Path(file_info['path'])
            if not file_path.exists():
                if self.logger:
                    self.logger.error(f"File does not exist: {file_info['path']}")
                return False
            hash_value = file_info.get('hash', '')
            if not hash_value or len(hash_value) != 64:
                if self.logger:
                    self.logger.error(f"Invalid hash for: {file_info['name']}")
                return False
            try:
                current_hash = self.calculate_sha256(file_path)
            except Exception:
                return False
            if current_hash != hash_value:
                if self.logger:
                    self.logger.error(f"Hash mismatch: {file_info['name']}")
                return False
        _hb_note(f'verify PASS {len(files_info)} file(s)')
        return True
    
    # ========================================================================
    # ТРАНСЛИТЕРАЦИЯ
    # ========================================================================
    def _cyrillic_to_latin(self, text: str) -> str:
        """Транслитерира кирилица на латиница"""
        cyrillic_map = {
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
            'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            ' ': ' ', '-': '-', '_': '_', '(': '(', ')': ')', '[': '[', ']': ']',
            '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
            '7': '7', '8': '8', '9': '9'
        }
        return ''.join(cyrillic_map.get(c, c) for c in text)
    
    def _sanitize_filename_for_display(self, filename: str) -> str:
        """Почиства име на файл за показване в PDF"""
        transliterated = self._cyrillic_to_latin(filename)
        return re.sub(r'\s+', ' ', transliterated)
    
    # ========================================================================
    # МЕТОДИ ЗА PDF СТИЛОВЕ И ТАБЛИЦИ
    # ========================================================================
    def _calculate_column_widths(self, proportions: Dict[str, float]) -> List[float]:
        """Изчислява ширините на колоните на база пропорции"""
        return [self.table_width * prop for prop in proportions.values()]
    
    def _apply_table_style(self, table, table_type='standard'):
        """Прилага глобалния стил на таблица (всички правила идват от style/*.js)."""
        # ReportLab TableStyle TEXTCOLOR does not override a Paragraph's own
        # textColor. Re-style only header Paragraphs; preserve every cell value.
        from reportlab.platypus import Paragraph as _HeaderParagraph
        from copy import copy as _copy_style
        for _col, _cell in enumerate(table._cellvalues[0]):
            if isinstance(_cell, _HeaderParagraph):
                _white_style = _copy_style(_cell.style)
                _white_style.textColor = colors.white
                table._cellvalues[0][_col] = _HeaderParagraph(_cell.text, _white_style)
        _globalize_table(table)

    def _create_base_styles(self, base_styles):
        """Създава базовите стилове за PDF с правилен wordWrap за европейски езици"""
        rules = _core_style_snapshot()
        # Стил за timestamp с Unicode шрифт, ако е наличен
        timestamp_font = _unicode_font('Helvetica')
        _unicode_stylesheet(base_styles)
        
        return {
            'title_style': ParagraphStyle('CustomTitle', parent=base_styles['Heading1'],
                **_factory_layout('title_style', rules)),
            'legal_style': ParagraphStyle('LegalStyle', parent=base_styles['Normal'],
                **_factory_layout('legal_style', rules)),
            'normal_style': base_styles['Normal'],
            'small_style': ParagraphStyle('Small', parent=base_styles['Normal'],
                **_factory_layout('small_style', rules)),
            'warning_style': ParagraphStyle('WarningStyle', parent=base_styles['Normal'],
                **_factory_layout('warning_style', rules)),
            'success_style': ParagraphStyle('SuccessStyle', parent=base_styles['Normal'],
                **_factory_layout('success_style', rules)),
            'table_text_style': ParagraphStyle('TableText', parent=base_styles['Normal'],
                **_factory_layout('table_text_style', rules)),
            'hash_style': ParagraphStyle('HashStyle', parent=base_styles['Normal'],
                **_factory_layout('hash_style', rules)),
            'header_style': ParagraphStyle('HeaderStyle', parent=base_styles['Normal'],
                **_factory_layout('header_style', rules)),
            'legal_declaration_style': ParagraphStyle('LegalDeclaration', parent=base_styles['Normal'],
                **_factory_layout('legal_declaration_style', rules)),
            'timestamp_style': ParagraphStyle('TimestampStyle', parent=base_styles['Normal'],
                **{**_factory_layout('timestamp_style', rules), 'fontName': timestamp_font})
        }
    
    def _create_explanatory_styles(self, base_styles):
        """Създава стилове за пояснителния документ"""
        rules = _core_style_snapshot()
        _unicode_stylesheet(base_styles)
        return {
            'normal_style': base_styles['Normal'],
            'small_style': ParagraphStyle('SmallExplanatory', parent=base_styles['Normal'],
                **_factory_layout('explanatory_small_style', rules)),
            'heading_style': ParagraphStyle('ExplanatoryHeading', parent=base_styles['Heading2'],
                **_factory_layout('explanatory_heading_style', rules)),
            'subheading_style': ParagraphStyle('ExplanatorySubheading', parent=base_styles['Heading3'],
                **_factory_layout('explanatory_subheading_style', rules)),
            'table_header_style': ParagraphStyle('ExplanatoryTableHeader', parent=base_styles['Normal'],
                **_factory_layout('explanatory_table_header_style', rules)),
            'table_cell_style': ParagraphStyle('ExplanatoryTableCell', parent=base_styles['Normal'],
                **_factory_layout('explanatory_table_cell_style', rules))
        }
    
    # ========================================================================
    # СЕКЦИИ ЗА PDF ДОКУМЕНТИ
    # ========================================================================
    def _add_system_info_section(self, story, styles, now, timezone_str, report_id, 
                                  files_info=None, single_file=False,
                                  rfc3161_timestamp=None, selection_filters=None):
        """Добавя секция със системна информация и timestamp"""
        normal_style = styles['normal_style']
        small_style = styles['small_style']
        warning_style = styles['warning_style']
        timestamp_style = styles['timestamp_style']
        
        # Винаги генерираме нов уникален timestamp за този отчет
        if rfc3161_timestamp is None:
            rfc3161_timestamp = self._get_rfc3161_timestamp(force_new=True)
        
        data_style = block_data_style(normal_style)
        story.append(block_heading("System Information (Beweissicherung)"))
        story.append(Paragraph(f"<b>Generated:</b> {self._format_datetime_ms(now)}", data_style))
        story.append(Paragraph(f"<b>Report ID:</b> {report_id}", data_style))
        
        if single_file:
            story.append(Paragraph(f"<b>Report Type:</b> Individual File Hash Report", data_style))
            if files_info and len(files_info) > 0:
                file_data = files_info[0]
                display_name = self._sanitize_filename_for_display(file_data['name'])
                story.append(Paragraph(f"<b>File Name:</b> {display_name}", data_style))
                story.append(Paragraph(f"<b>File Size:</b> {self._format_kb(file_data['size'])}", data_style))
                story.append(Paragraph("<b>File Hashes:</b>", data_style))
                file_hashes = self._court_file_hashes(file_data['path'])
                if file_hashes['SHA-256'].lower() != file_data['hash'].lower():
                    raise RuntimeError("File changed since initial SHA-256 calculation")
                self._add_aligned_key_value_table(
                    story, list(file_hashes.items()), styles, label_ratio=0.18, compact=True)
        else:
            story.append(Paragraph(f"<b>Report Type:</b> Combined File Hash Report (Evidence Package)", data_style))
            if files_info:
                story.append(Paragraph(f"<b>Total Files:</b> {len(files_info)}", data_style))
                total_size = sum(f['size'] for f in files_info)
                story.append(Paragraph(f"<b>Total Size:</b> {self._format_kb(total_size)}", data_style))
                total_checksums = self._court_hashes(self._aggregate_checksum_payload(files_info))
                from xml.sax.saxutils import escape as _xml_escape
                if selection_filters:
                    filter_text = ", ".join(_xml_escape(str(item)) for item in selection_filters)
                else:
                    filter_text = "none - every file in the folder"
                story.append(Paragraph(
                    f"<b>Selection filter:</b> {filter_text}", data_style))
                story.append(Paragraph("<b>Total Checksum (All Files):</b>", data_style))
                # v2.34: fixed label column for every checksum.
                story.append(Spacer(1, ReportConstants.SPACER_TABLE))
                self._add_aligned_key_value_table(
                    story, list(total_checksums.items()), styles, label_ratio=0.18, compact=True)
        
        from chronoseal_volume_report import append_volume_section
        _work_dir = Path(files_info[0]['path']).parent if files_info and files_info[0].get('path') else None
        append_volume_section(story, normal_style, _work_dir)
        story.append(block_heading("User Information"))
        story.append(Paragraph(f"<b>Generated by:</b> {self.user_info.get('username', 'Unknown')}", data_style))
        story.append(Paragraph(f"<b>Computer Name:</b> {self.system_info.get('computer_name', 'Unknown')}", data_style))
        story.append(Paragraph(f"<b>Operating System:</b> {self.system_info.get('os', 'Unknown')} {self.system_info.get('os_version', '')}", data_style))
        story.append(Paragraph(f"<b>Hardware ID:</b> {self.system_info.get('hardware_id', 'Unknown')}", data_style))
        
        # v2.34: protocol-wide information is shown once. START/STOP contain
        # only the data and validation result of their respective TSA signature.
        self._add_timestamp_general_section(story, styles, single_file=single_file)
        start_heading_style = ParagraphStyle('TimestampStartHeadingV233', parent=normal_style, keepWithNext=True)
        story.append(block_heading("Cryptographic Timestamp START"))
        if rfc3161_timestamp:
            self._add_timestamp_block(
                story, styles, rfc3161_timestamp,
                display_marker='START', signature_only=True, show_internal_heading=False)
        else:
            story.append(Paragraph("<i>No timestamp available</i>", warning_style))
    
    def _add_rfc3161_base64_at_document_end(self, story, styles):
        """Backward-compatible wrapper for v2.23 callers."""
        self._add_rfc3161_tokens_at_document_end(story, styles)

    def _add_legal_declaration(self, story, styles, now, timezone_str, is_combined=True):
        """Machine-generated technical statement, not an affidavit."""
        from xml.sax.saxutils import escape
        style = styles['legal_declaration_style']
        username = escape(str(self.user_info.get('username', 'Unknown')))
        computer_name = escape(str(self.system_info.get('computer_name', 'Unknown')))
        scope_de = 'aufgeführten Dateien' if is_combined else 'aufgeführten Datei'
        scope_en = 'listed files' if is_combined else 'listed file'
        stamp = escape(now.strftime('%d.%m.%Y %H:%M:%S.%f')[:-3])
        tz = escape(str(timezone_str))
        story.append(block_heading('Technischer Erzeugungsvermerk (keine eidesstattliche Versicherung)'))
        text = (
            f'Der Generator protokolliert SHA-256-Werte der {scope_de}. '
            f'Lokaler Erzeugungszeitpunkt: {stamp} ({tz}); '
            f'System: {computer_name}; Benutzerkonto: {username}. '
            'Diese Angaben stammen aus der lokalen Systemumgebung und sind keine '
            'unabhaengige Bestaetigung der Herkunft, Urheberschaft oder Existenz '
            'einer Originaldatei zu einem frueheren Zeitpunkt. '
            'Die Hashwerte koennen nur anhand der tatsaechlichen Dateibytes '
            'unabhaengig nachgerechnet werden.<br/><br/>'
            '<b>Automated technical record (not an affidavit):</b><br/>'
            f'The generator records SHA-256 values for the {scope_en}. '
            f'Local generation time: {stamp} ({tz}); system: {computer_name}; '
            f'account: {username}. These local metadata do not independently '
            'establish file origin, authorship, or earlier existence. '
            'Hashes require independent recalculation against the actual files.<br/><br/>'
            '<b>Pruefumfang / Verification scope:</b> '
            'The final PDF signature, TSA trust chain, revocation status and '
            'evidence-file hashes must each be verified separately. '
            'No legal qualification is implied by this automated record.<br/><br/>'
        )
        story.append(Paragraph(text, style))

    def _add_footer(self, story, styles, now, timezone_str, is_combined=False):
        """Добавя footer на документа"""
        small_style = styles['small_style']
        story.append(Spacer(1, ReportConstants.SPACER_AFTER_DECLARATION))
        if is_combined:
            footer_text = "This report documents the listed file hashes and the RFC 3161 START/STOP evidence shown above."
        else:
            footer_text = "This report documents the listed file hash and the RFC 3161 START/STOP evidence shown above."
        story.append(Paragraph(footer_text, small_style))
        story.append(Paragraph("Report engine: PasevSU Hash Report Generator v2.34 (technical component); CRYPTO REPORT ENTERPRICE v5.5.3-RC (report presentation). No court certification implied.", small_style))
        story.append(Paragraph("SHA-256 is used here as a cryptographic digest; legal evaluation remains case-specific.", small_style))
        story.append(Paragraph("Created and licensed by Home Assistant Projects · PasevSU DEV · part of the NO TRUST Cybersecurity volunteer campaign.", small_style))
    
    def _generate_explanatory_pdf(self, output_path: Union[str, Path]) -> Path:
        """Generate the explanatory/legal reading guide as a separate PDF.

        It is intentionally not part of the cryptographically closed hash report.
        """
        output_path = Path(output_path)
        from hash_report_generator.a4_document import A4DocTemplate
        doc = A4DocTemplate(str(output_path))
        base_styles = getSampleStyleSheet()
        story = []
        self._add_explanatory_page(story, base_styles, start_on_new_page=False)
        # v2.34: this companion is explicitly outside the Hash Report and therefore
        # carries no report page numbering at all.
        doc.build(story, canvasmaker=UnnumberedCanvas)
        return output_path

    def _add_explanatory_page(self, story, base_styles, start_on_new_page=True):
        """Add the explanatory document. v2.34 normally writes it to a separate PDF."""
        if start_on_new_page:
            story.append(PageBreak())
        
        expl_styles = self._create_explanatory_styles(base_styles)
        normal_style = expl_styles['normal_style']
        small_style = expl_styles['small_style']
        heading_style = expl_styles['heading_style']
        subheading_style = expl_styles['subheading_style']
        table_header_style = expl_styles['table_header_style']
        table_cell_style = expl_styles['table_cell_style']
        
        story.append(Paragraph("ERLÄUTERNDES DOKUMENT ZUM „SHA-256 HASH REPORT – KRYPTOGRAPHISCHER EXISTENZNACHWEIS“", heading_style))
        story.append(Spacer(1, ReportConstants.SPACER_HEADING))
        story.append(Paragraph("Technische Prüfanleitung und rechtliche Einordnung - separates Begleitdokument", subheading_style))
        story.append(Spacer(1, ReportConstants.SPACER_SUBHEADING))
        
        story.append(Paragraph("<b>RECHTLICHE GRUNDLAGEN FÜR DEUTSCHE GERICHTE</b>", normal_style))
        story.append(Spacer(1, ReportConstants.SPACER_SECTION))
        
        legal_table_data = [[
            Paragraph("<b>Gesetz / Entscheidung</b>", table_header_style),
            Paragraph("<b>Bedeutung für den Hash Report</b>", table_header_style)
        ]]
        legal_rows = [
            ("§ 286 ZPO (Zivilprozessordnung)", "Das Gericht würdigt Beweise nach seiner freien Überzeugung. Die technische Dokumentation unterliegt der freien Beweiswürdigung im konkreten Verfahren."),
            ("§ 371 ZPO", "Ist eine elektronische Datei Gegenstand des Beweises, erfolgt der Beweisantritt durch Vorlegung oder Übermittlung der Datei. Ein übereinstimmender Hash dokumentiert Byte-Gleichheit zur referenzierten Datei."),
                        ("§ 156 StGB (nur bei gesonderter Versicherung an Eides statt)", "Die Strafnorm betrifft falsche Versicherungen an Eides statt, soweit eine solche rechtlich vorgesehen und tatsächlich abgegeben wird. Dieser automatisch erstellte technische Bericht enthält keine Versicherung an Eides statt."),
                        ("Art. 41 eIDAS (EU) Nr. 910/2014", "Ein elektronischer Zeitstempel darf nicht allein wegen seiner elektronischen Form oder fehlender Qualifikation als Beweismittel zurückgewiesen werden; die besondere Vermutungswirkung gilt für qualifizierte Zeitstempel.")
        ]
        for row in legal_rows:
            legal_table_data.append([Paragraph(row[0], table_cell_style), Paragraph(row[1], table_cell_style)])
        legal_table = Table(legal_table_data, repeatRows=1, colWidths=self._calculate_column_widths(ReportConstants.LEGAL_TABLE_COL_PROPORTIONS))
        self._apply_table_style(legal_table, table_type='explanatory')
        story.append(legal_table)
        story.append(Spacer(1, ReportConstants.SPACER_SUBHEADING))
        
        story.append(Paragraph("<b>1. AUTHENTIZITÄT DES REPORTS (SHA-256-HASH)</b>", normal_style))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))
        story.append(Paragraph("Der Report enthält den SHA-256-Hash-Wert der geprüften Datei. SHA-256 ist eine kollisionsresistente kryptographische Prüfsumme. Ein übereinstimmender Hash:", small_style))
        story.append(Paragraph("• dokumentiert, dass die verglichenen Bytefolgen denselben SHA-256-Wert besitzen;", small_style))
        story.append(Paragraph("• mit einem Befehl überprüft werden kann: <i>sha256sum [Datei]</i>;", small_style))
        story.append(Paragraph("<b>Rechtliche Grundlage:</b> Stimmt der neu berechnete Hash mit dem im Report überein, ist die geprüfte Bytefolge mit der referenzierten Bytefolge kryptographisch konsistent. Die rechtliche Würdigung erfolgt im Einzelfall.", small_style))
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        story.append(Paragraph("<b>2. AUTOMATISCHE GENERIERUNG (TECHNISCHE UNABHÄNGIGKEIT)</b>", normal_style))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))
        tech_table_data = [[Paragraph("<b>Element</b>", table_header_style), Paragraph("<b>Was es beweist</b>", table_header_style)]]
        tech_rows = [
            ("Hardware ID", "Lokale Systemkennung zur technischen Protokollierung; kein unabhängiger Identitätsnachweis"),
            ("RFC 3161 Timestamp", "Falls im Report als erfolgreich verifiziert ausgewiesen: signierter Zeitstempel einer unabhängigen TSA. Der Client verwendet Primary + 3 Alternativen (DFN, DigiCert, GlobalSign, Sectigo) mit automatischem Failover. Bei Status UNAVAILABLE liegt kein TSA-Zeitnachweis vor."),
            ("Generated (CET/CEST)", "Systemzeit des Computers, der den Report erstellt hat")
        ]
        for row in tech_rows:
            tech_table_data.append([Paragraph(row[0], table_cell_style), Paragraph(row[1], table_cell_style)])
        tech_table = Table(tech_table_data, repeatRows=1, colWidths=self._calculate_column_widths(ReportConstants.TECH_TABLE_COL_PROPORTIONS))
        self._apply_table_style(tech_table, table_type='explanatory')
        story.append(tech_table)
        story.append(Spacer(1, ReportConstants.SPACER_SECTION))
        story.append(Paragraph("<b>Technische Bedeutung:</b> Ein erfolgreich verifizierter RFC-3161-Token bindet den im Token enthaltenen Message Imprint an die von der TSA angegebene Zeit. Lokale Systemzeit und Hardwaredaten sind ergänzende Metadaten und kein unabhängiger Zeitnachweis.", small_style))
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        if self.include_ots:
            story.append(Paragraph("<b>3. OPENTIMESTAMPS (OTS) – FALLS ENTHALTEN</b>", normal_style))
            story.append(Spacer(1, ReportConstants.SPACER_TABLE))
            story.append(Paragraph("Wenn der Report OTS-Informationen enthält, beweist dies:", small_style))
            story.append(Paragraph("• dass ein anderes Dokument zum Zeitpunkt der Erstellung existierte;", small_style))
            story.append(Paragraph("• dass dieser Fakt in der Bitcoin-Blockchain festgehalten wurde – einem öffentlichen, unveränderlichen und unabhängigen Register;", small_style))
            story.append(Paragraph("• dass die vollständige Integrität der geprüften Datei nachgewiesen wird.", small_style))
            story.append(Paragraph("<b>Rechtliche Grundlage:</b> Blockchain-Aufzeichnungen werden gemäß der Rechtsprechung deutscher Gerichte (einschließlich BGH) als unwiderlegbarer Beweis für den Zeitpunkt der Existenz anerkannt.", small_style))
            story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        story.append(Paragraph("<b>WIE KANN DAS GERICHT ODER DIE STAATSANWALTSCHAFT PRÜFEN?</b>", normal_style))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))
        steps = [
            ("<b>SCHRITT 1 – Hash-Prüfung:</b>", "Get-FileHash \"[zu_pruefende_Datei]\" -Algorithm SHA256 / Vergleich mit dem Hash im Report"),
            ("<b>SCHRITT 2 – RFC-3161-Prüfung:</b>", "TSA-Token kryptographisch prüfen; SHA-256 Message Imprint und Nonce mit der Anfrage bzw. dem geprüften Hash vergleichen. Status UNAVAILABLE bedeutet: kein unabhängiger TSA-Zeitnachweis."),
            ("<b>SCHRITT 3 – Hardware ID:</b>", "Lokale Systemkennung nur ergänzend vergleichen; sie ist kein kryptographischer Identitätsnachweis"),
            ("<b>SCHRITT 4 – Digitale PDF-Signatur (falls vorhanden):</b>", "Öffnen mit Adobe Acrobat Reader → 'Signaturen' / Status: 'Die Signatur ist gültig'")
        ]
        for step_title, step_desc in steps:
            story.append(Paragraph(f"{step_title} {step_desc}", small_style))
            story.append(Spacer(1, ReportConstants.SPACER_MICRO))
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        summary_table_data = [[
            Paragraph("<b>Was beweist der Report?</b>", table_header_style),
            Paragraph("<b>Wie wird es geprüft?</b>", table_header_style),
            Paragraph("<b>Rechtliche Grundlage</b>", table_header_style)
        ]]
        summary_rows = [
            ("Byte-Gleichheit zur Referenz", "SHA-256 neu berechnen + vergleichen", "Technischer Nachweis; Würdigung nach § 286 ZPO"),
            ("Zeitbindung des Message Imprint (nur bei gültigem RFC-3161-Token)", "TSA-Token, Signatur, Imprint und Nonce prüfen", "Technischer Nachweis; gerichtliche Würdigung nach den Umständen des Einzelfalls"),
            ("OTS / Blockchain (nur bei beigefügtem und geprüftem OTS-Nachweis)", "OTS-Proof, Dateihash und Blockchain-Anker separat verifizieren; ohne OTS-Proof kein OTS-Nachweis", "Technischer Zusatznachweis; nicht Bestandteil dieses RFC-3161-Berichts, sofern nicht ausdrücklich beigefügt"),
            ("Versicherung an Eides statt (nicht enthalten)", "Nur ein eigenständiger, tatsächlich abgegebener und rechtlich zulässiger Erklärungstext wäre gesondert zu prüfen", "§ 156 StGB nur bei Vorliegen der gesetzlichen Voraussetzungen")
        ]
        for row in summary_rows:
            summary_table_data.append([Paragraph(row[0], table_cell_style), Paragraph(row[1], table_cell_style), Paragraph(row[2], table_cell_style)])
        summary_table = Table(summary_table_data, repeatRows=1, colWidths=self._calculate_column_widths(ReportConstants.SUMMARY_TABLE_COL_PROPORTIONS))
        self._apply_table_style(summary_table, table_type='explanatory')
        try:
            from .pagination_policy import keep_short_section
        except ImportError:
            from pagination_policy import keep_short_section
        summary_heading = Paragraph("<b>ZUSAMMENFASSUNG</b>", normal_style)
        _kept = keep_short_section(
            summary_heading, summary_table, gap_pt=ReportConstants.SPACER_TABLE,
        )
        story.extend(_kept if isinstance(_kept, list) else [_kept])
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        try:
            from .pagination_policy import keep_heading_with_first_paragraph
        except ImportError:
            from pagination_policy import keep_heading_with_first_paragraph
        procedural_heading = Paragraph(
            "<b>VERFAHRENSHINWEISE FÜR DAS GERICHT</b>", normal_style,
        )
        first_procedural_note = Paragraph(
            "1. Dieses Begleitdokument erläutert die reproduzierbaren technischen "
            "Prüfschritte des separat erzeugten Hash Reports.",
            small_style,
        )
        _kept = keep_heading_with_first_paragraph(
            procedural_heading, first_procedural_note,
            gap_pt=ReportConstants.SPACER_TABLE,
        )
        story.extend(_kept if isinstance(_kept, list) else [_kept])
        story.append(Paragraph("2. Die konkrete Beweiswürdigung bleibt dem zuständigen Gericht anhand des gesamten Verfahrensinhalts vorbehalten.", small_style))
        story.append(Paragraph("3. Bei Widerspruch sollte das Gericht:", small_style))
        story.append(Paragraph("   • Einen forensischen EDV-Sachverständigen bestellen;", small_style))
        story.append(Paragraph("   • Die oben genannten technischen Prüfungen durchführen;", small_style))
        story.append(Paragraph("   • Die Grundsätze des § 286 ZPO zur freien Beweiswürdigung anwenden.", small_style))
        story.append(Paragraph("<i>Hinweis: Dieses Begleitdokument ist keine gerichtliche Bewertung und keine Vorgabe für die Beweiswürdigung.</i>", small_style))
        story.append(Spacer(1, ReportConstants.SPACER_PARAGRAPH))
        
        story.append(Paragraph("<b>ABSCHLIEßENDE ERKLÄRUNG</b>", normal_style))
        story.append(Spacer(1, ReportConstants.SPACER_TABLE))
        story.append(Paragraph("Dieses Dokument dient dazu, das Gericht und die Staatsanwaltschaft bei der korrekten rechtlichen und technischen Bewertung des beigefügten SHA-256-Hash-Reports zu unterstützen. Es enthält die erforderlichen rechtlichen Grundlagen und technischen Anweisungen, damit die enthaltenen kryptographischen Angaben unabhängig nachvollzogen und im jeweiligen Verfahren sachgerecht gewürdigt werden können.", small_style))
        story.append(Spacer(1, ReportConstants.SPACER_SECTION))
        story.append(Paragraph("<i>Dieses Begleitdokument wird getrennt vom Hash Report erzeugt und ist nicht Bestandteil des kryptographisch geschlossenen Reports.</i>", small_style))
        return story