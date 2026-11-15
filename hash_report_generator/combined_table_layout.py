"""Shared lossless COMBO table cell formatting (no truncation)."""
import re
from xml.sax.saxutils import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Paragraph

try:
    from .pdf_object_rules import display_hash
except ImportError:
    from pdf_object_rules import display_hash

def index_cell(index, base_style):
    style = ParagraphStyle('ChronoSealIndex', parent=base_style, alignment=TA_CENTER, wordWrap=None)
    return Paragraph(str(index), style)


def size_kb_cell(value):
    """Header already declares KB; avoid redundant unit inside each row."""
    return re.sub(r'\s*KB\s*$', '', str(value), flags=re.I)


def digest_cell(digest, style, group=16):
    """Wrap a full hexadecimal digest on fixed boundaries without losing bytes."""
    if not re.fullmatch(r'[a-fA-F0-9]{64}', str(digest)):
        return Paragraph(escape(str(digest)), style)
    digest = display_hash(digest)
    return Paragraph('<br/>'.join(digest[i:i+group] for i in range(0, len(digest), group)), style)


def timestamp_cell(value, style):
    """Format an ISO-like timestamp on two lines without changing its content."""
    text = str(value)
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2})[ T](.+)', text)
    if match:
        text = f"{escape(match.group(1))}<br/>{escape(match.group(2))}"
    else:
        text = escape(text)
    return Paragraph(text, style)


def digest_cell_for_width(digest, style, width):
    """Wrap a complete digest into readable groups sized to its table column."""
    if not re.fullmatch(r'[a-fA-F0-9]{64}', str(digest)):
        return Paragraph(escape(str(digest)), style)
    font_size = max(float(getattr(style, "fontSize", 7)), 1.0)
    group = max(8, min(32, int(float(width) / (font_size * 0.62))))
    group = max(8, group - group % 4)
    return digest_cell(str(digest), style, group=group)


def safe_text_cell(value, style):
    """Create a ReportLab paragraph with markup-safe plain text."""
    return Paragraph(escape(str(value)), style)
