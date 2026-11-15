"""SINGLE SOURCE OF TRUTH: PDF object rules for ChronoSeal ReportLab and CSS.
All design values belong here. No cryptographic operations are performed here.
"""

# Unified report import bootstrap: supports script, GUI and package invocation.
import sys as _report_sys
from pathlib import Path as _report_Path
_report_dir = _report_Path(__file__).resolve().parent
for _report_path in (str(_report_dir.parent), str(_report_dir)):
    if _report_path not in _report_sys.path:
        _report_sys.path.insert(0, _report_path)



# Support direct execution from hash_report_generator and package imports.
import sys as _cs_sys
from pathlib import Path as _cs_Path
_cs_root = str(_cs_Path(__file__).resolve().parents[1])
if _cs_root not in _cs_sys.path:
    _cs_sys.path.insert(0, _cs_root)

from hash_report_generator.style_runtime import visual as _central_visual
from dataclasses import dataclass
try:
    from .style_loader import load_styles as _load_styles
except ImportError:
    from style_loader import load_styles as _load_styles
_STYLE = _load_styles()
PAGE = _STYLE["PAGE"]
COLORS = _STYLE["COLORS"]
FONTS = _STYLE["FONTS"]
LEADING = _STYLE["LEADING"]
TABLE = _STYLE["TABLE"]
TABLE_RELIEF = _STYLE["TABLE_RELIEF"]
COLUMNS = _STYLE["COLUMNS"]
OBJECTS = _STYLE["OBJECTS"]
LEGAL_CONTAINER = _STYLE["LEGAL_CONTAINER"]
KEY_VALUE = _STYLE["KEY_VALUE"]
SIZE_UNIT = _STYLE["SIZE_UNIT"]
TITLE_HIERARCHY = _STYLE["TITLE_HIERARCHY"]
FONT_FAMILIES = _STYLE["FONT_FAMILIES"]
FONT_FILES = _STYLE["FONT_FILES"]
FONT_POLICY = _STYLE["FONT_POLICY"]
BRIDGE_LAYOUT = _STYLE["BRIDGE_LAYOUT"]




_BUILTIN_FONT_ROLES = {
    "Helvetica": "regular", "Helvetica-Bold": "bold",
    "Helvetica-Oblique": "italic", "Helvetica-BoldOblique": "bold_italic",
    "Courier": "monospace", "Courier-Bold": "monospace_bold",
}


def unicode_font(name):
    """Map a legacy built-in (non-Cyrillic) font name from any rule file to the central Unicode family."""
    role = _BUILTIN_FONT_ROLES.get(name)
    return font_name(role) if role else name


def _register_family():
    """Make <b>/<i> markup resolve to the Unicode bold/italic faces once all four are available."""
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    roles = ("regular", "bold", "italic", "bold_italic")
    faces = {}
    for role in roles:
        for candidate in FONT_POLICY.get("system_font_candidates", {}).get(role, []):
            if Path(candidate).is_file():
                faces[role] = (FONT_FAMILIES[role], candidate)
                break
        else:
            return
    for name, path in faces.values():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        FONT_FAMILIES["regular"], normal=FONT_FAMILIES["regular"], bold=FONT_FAMILIES["bold"],
        italic=FONT_FAMILIES["italic"], boldItalic=FONT_FAMILIES["bold_italic"])


def unicode_stylesheet(base_styles):
    """Remap every built-in font of a ReportLab stylesheet to the central Unicode family."""
    for style in base_styles.byName.values():
        if hasattr(style, "fontName"):
            style.fontName = unicode_font(style.fontName)
    return base_styles


def font_name(role="regular"):
    """Resolve a declarative font role; register an optional local TTF file."""
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    name = FONT_FAMILIES[role]
    # One centralized font policy for all report profiles.
    candidates = FONT_POLICY.get("system_font_candidates", {}).get(role, [])
    if candidates:
        for candidate in candidates:
            path = Path(candidate)
            if path.is_file():
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, str(path)))
                _register_family()
                return name
        raise FileNotFoundError(f"Required Unicode font for {role} not found: {candidates}")
    relative = FONT_FILES.get(role)
    if relative:
        path = (Path(__file__).resolve().parent / "style" / relative).resolve()
        root = (Path(__file__).resolve().parent / "style").resolve()
        if not path.is_relative_to(root):
            raise ValueError("Font path escapes style directory")
        if not path.is_file():
            if not FONT_POLICY["fallback_to_builtin"]:
                raise FileNotFoundError(f"Required font missing: {path}")
            return "Helvetica-Bold" if role in ("bold", "bold_italic") else "Helvetica"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    elif FONT_POLICY["require_embedded_unicode"]:
        raise ValueError(f"Unicode embedded font required for {role}")
    return name

def page_geometry():
    """Canonical ISO A4 coordinates; ReportLab origin is bottom-left (pt)."""
    from reportlab.lib.units import mm
    p = PAGE
    width, height = float(p['width_mm']), float(p['height_mm'])
    left, right = float(p['left_mm']), float(p['right_mm'])
    top, bottom = float(p['top_mm']), float(p['bottom_mm'])
    reserved = float(p['footer_reserved_mm'])
    pad = float(p['frame_padding_pt']) * 25.4 / 72.0
    if (abs(width-210)>0.01 or abs(height-297)>0.01 or
            min(left,right,top,bottom) < 0 or reserved < 0 or
            bottom < reserved + float(p.get('body_footer_gap_mm',0)) or
            width-left-right-2*pad < float(p.get('minimum_content_width_mm',1)) or
            height-top-bottom-2*pad <= 0):
        raise ValueError('Invalid canonical A4 page geometry')
    return dict(page_width_pt=width*mm,page_height_pt=height*mm,
        body_x_pt=(left+pad)*mm, body_y_pt=(bottom+pad)*mm,
        body_width_pt=(width-left-right-2*pad)*mm,
        body_height_pt=(height-top-bottom-2*pad)*mm,
        footer_top_pt=reserved*mm, footer_bottom_pt=0,
        left_margin_pt=left*mm,right_margin_pt=right*mm,
        top_margin_pt=top*mm,bottom_margin_pt=bottom*mm)

def content_width_mm():
    return page_geometry()['body_width_pt'] * 25.4 / 72

def validate():
    assert page_geometry()["body_width_pt"]>0
    for key, widths in COLUMNS.items():
        assert abs(sum(widths.values())-1)<1e-9, key
    assert COLORS["header_text"] != COLORS["accent"]
    assert all(role in FONT_FAMILIES for role in ("regular", "bold", "italic", "bold_italic", "monospace"))
    return True

def reportlab_constants():
    return dict(TABLE_WIDTH_MM=content_width_mm(), COMBINED_TABLE_COL_PROPORTIONS_7=COLUMNS["combined"],
        INFO_TABLE_COL_PROPORTIONS=COLUMNS["info"],LEGAL_TABLE_COL_PROPORTIONS=COLUMNS["legal"],
        TECH_TABLE_COL_PROPORTIONS=COLUMNS["technical"],SUMMARY_TABLE_COL_PROPORTIONS=COLUMNS["summary"],
        CERT_TABLE_COL_PROPORTIONS=COLUMNS["certificate"],TIMESTAMP_TABLE_COL_PROPORTIONS=COLUMNS["timestamp"],
        OTS_TABLE_COL_PROPORTIONS=COLUMNS["ots"], TABLE_PADDING=TABLE["padding_pt"],
        TABLE_HEADER_BOTTOM_PADDING=TABLE["header_bottom_padding_pt"],
        FONT_SIZE_TITLE=FONTS["title"],FONT_SIZE_HEADING=FONTS["heading"],
        FONT_SIZE_TABLE_HEADER=FONTS["table_header"],FONT_SIZE_TABLE_TEXT=FONTS["table_text"],
        FONT_SIZE_TABLE_HASH=FONTS["table_hash"])

def css_text():
    return f"""/* GENERATED FROM pdf_object_rules.py: DO NOT EDIT */
@page {{ size: A4; margin: {PAGE["top_mm"]}mm {PAGE["right_mm"]}mm {PAGE["bottom_mm"]}mm {PAGE["left_mm"]}mm; }}
html,body {{font-family:"{FONT_FAMILIES["regular"]}";color:{COLORS["ink"]};font-size:{FONTS["body"]}pt;line-height:{LEADING["body"]}pt;}}
h1 {{font-size:{TITLE_HIERARCHY["h1"]["size_pt"]}pt;font-weight:bold;page-break-after:avoid;}}
h2 {{font-size:{TITLE_HIERARCHY["h2"]["size_pt"]}pt;font-weight:bold;page-break-after:avoid;}}
h3 {{font-size:{TITLE_HIERARCHY["h3"]["size_pt"]}pt;font-weight:normal;page-break-after:avoid;}}
.report-section-title {{font-size:{FONTS["heading"]}pt;color:{COLORS["accent"]};font-weight:bold;text-transform:uppercase;page-break-after:avoid;}}
p,li,.legal-note {{orphans:{_STYLE["PAGINATION"].get("minimum_orphan_lines",3)};widows:{_STYLE["PAGINATION"].get("minimum_widow_lines",3)};overflow-wrap:anywhere;}}
.legal-note {{background:{LEGAL_CONTAINER["background"] if "LEGAL_CONTAINER" in globals() else "#f1f2f4"};font-size:{FONTS["legal"]}pt;padding:{LEGAL_CONTAINER.get("padding_pt",7)}pt;}}
table {{width:100%;border-collapse:collapse;table-layout:fixed;}}
thead {{display:table-header-group;}}
tr {{page-break-inside: avoid;}}
th,td {{vertical-align:top;padding:{TABLE["padding_pt"]}pt;border-bottom:.25pt solid {COLORS["grid"]};overflow-wrap:anywhere;}}
th,th p,th span {{background:{COLORS["accent"]};color:{COLORS["header_text"]}!important;}}
.hash,.digest {{font-family:"{FONT_FAMILIES["monospace"]}";font-size:{FONTS["table_hash"]}pt;overflow-wrap:anywhere;}}
.report-footer {{font-size:{FONTS["footer"]}pt;color:{COLORS["muted"]};}}
img,svg,.qr {{max-width:100%;height:auto;}}
"""
validate()


def block_heading(label):
    """Block-opening label: uppercase, bold, identical spacing before every block."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib import colors
    rule = _STYLE["BLOCK_TEXT"]
    style = ParagraphStyle(
        "CentralBlockHeading", fontName=font_name("bold"), fontSize=rule["heading_font_size_pt"],
        leading=rule["heading_leading_pt"], textColor=colors.HexColor(rule["heading_color"]),
        spaceBefore=rule["heading_space_before_pt"], spaceAfter=rule["heading_space_after_pt"],
        keepWithNext=1)
    return Paragraph(section_heading_markup(label), style)


def block_data_style(parent):
    """Data lines under a block heading: central size/colour, one step below the heading."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    rule = _STYLE["BLOCK_TEXT"]
    return ParagraphStyle(
        "CentralBlockData", parent=parent, fontName=font_name("regular"),
        fontSize=rule["data_font_size_pt"], leading=rule["data_leading_pt"],
        textColor=colors.HexColor(rule["data_color"]), spaceBefore=0, spaceAfter=0)


def bridge_paragraph_style(name, key, parent=None, alignment=None):
    """Paragraph style for bridge elements, fully driven by BRIDGE_LAYOUT.paragraph_styles."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    rule = BRIDGE_LAYOUT["paragraph_styles"][key]
    kwargs = dict(
        fontSize=rule["font_pt"], leading=rule["leading_pt"],
        textColor=colors.HexColor(BRIDGE_LAYOUT["colors"][rule["color"]]),
        spaceBefore=rule.get("space_before_pt", 0), spaceAfter=rule.get("space_after_pt", 0),
        leftIndent=rule.get("left_indent_pt", 0))
    if rule.get("font"):
        kwargs["fontName"] = unicode_font(rule["font"])
    if alignment is not None:
        kwargs["alignment"] = alignment
    if parent is not None:
        kwargs["parent"] = parent
    return ParagraphStyle(name, **kwargs)


def display_hash(value):
    """Uppercase hexadecimal digests for display only (never for verification)."""
    import re
    text = str(value)
    if _STYLE["HASH_DISPLAY"]["uppercase"] and re.fullmatch(r"[0-9a-fA-F]{8,}", text):
        return text.upper()
    return text


def section_heading_markup(label: str) -> str:
    """Central rule for all block-opening labels; ReportLab Paragraph markup."""
    from xml.sax.saxutils import escape
    normalized = str(label).strip()
    if not normalized.endswith(":"):
        normalized += ":"
    return "<b>" + escape(normalized.upper()) + "</b>"

# Presentation rules: every report consumes these values, never an independent unit conversion.

def format_bytes(value):
    """Exact integer bytes; no lossy KB/MB rounding."""
    number = int(value)
    if number < 0: raise ValueError("File size cannot be negative")
    return f"{number:,} bytes".replace(",", " ")

def aligned_fields(story, pairs, paragraph_style, width_pt):
    """Aligned two-column labels/values; long values wrap in value column."""
    from reportlab.platypus import TableStyle, Paragraph
    Table = GlobalReportTable
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    label_width = width_pt * KEY_VALUE["label_ratio"]
    rows = [[Paragraph(f"<b>{escape(str(k).rstrip(':'))}:</b>", paragraph_style),
             Paragraph(escape(str(v)), paragraph_style)] for k,v in pairs]
    table = Table(rows, colWidths=[label_width, width_pt-label_width], hAlign=_central_visual('pdf_object_rules__L142__hAlign'))
    table.setStyle(aligned_fields_table_style())
    story.append(table)
    return table

def legal_panel(paragraph, width_pt):
    from reportlab.platypus import TableStyle
    Table = GlobalReportTable
    from reportlab.lib import colors
    t = Table([[paragraph]], colWidths=[width_pt], hAlign=_central_visual('pdf_object_rules__L156__hAlign'))
    t.setStyle(legal_panel_table_style())
    return t


# Unified rendering policy: no individual generator should choose its own
# body/heading/label/size presentation independently.


def heading_style(kind, base=None):
    """ReportLab paragraph style with the canonical heading hierarchy."""
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib import colors
    spec = TITLE_HIERARCHY[kind]
    return ParagraphStyle(
        "ChronoSeal_" + kind, parent=base or getSampleStyleSheet()["Normal"],
        fontName=font_name("bold" if spec["bold"] else "regular"),
        fontSize=spec["size_pt"], leading=spec["size_pt"] * 1.25,
        textColor=colors.HexColor(COLORS["accent"]),
        spaceBefore=5 if kind == "section" else 0,
        spaceAfter=_central_visual('pdf_object_rules__L183__spaceAfter'), keepWithNext=_central_visual('pdf_object_rules__L183__keepWithNext'),
    )


def legal_paragraph_style(base=None):
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib import colors
    return ParagraphStyle(
        "ChronoSealLegal", parent=base or getSampleStyleSheet()["Normal"],
        fontName=font_name("regular"), fontSize=FONTS["legal"],
        leading=LEADING["legal"], textColor=colors.HexColor(COLORS["ink"]),
        splitLongWords=_central_visual('pdf_object_rules__L194__splitLongWords'),
    )


def canonical_size(value):
    """Use for PDF display only. Do not change source-file hash input."""
    return format_bytes(value)


def validate_rendering_contract():
    validate()
    assert FONTS["legal"] < FONTS["body"]
    assert TITLE_HIERARCHY["h1"]["size_pt"] > TITLE_HIERARCHY["h2"]["size_pt"] > TITLE_HIERARCHY["h3"]["size_pt"]
    assert OBJECTS["table_size"]["unit"] == "bytes"
    assert KEY_VALUE["label_ratio"] > 0
    return True


# Shared concrete table rendering rules; called by report generators.
def table_header_paragraph(text, parent=None):
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    style = ParagraphStyle("ChronoSealTableHeader", parent=parent or getSampleStyleSheet()["Normal"],
        fontName=font_name("bold"), fontSize=FONTS["table_header"],
        leading=max(10, FONTS["table_header"] * 1.3),
        textColor=colors.HexColor(COLORS["header_text"]), alignment=_central_visual('pdf_object_rules__L221__alignment'))
    return Paragraph(escape(str(text)), style)


class ReliefTableMixin:
    """Paint a real offset shadow behind a ReportLab Table without resizing cells."""
    def drawOn(self, canv, x, y, _sW=0):
        from reportlab.lib import colors
        rule = TABLE_RELIEF
        canv.saveState()
        try:
            if hasattr(canv, "setFillAlpha"):
                canv.setFillAlpha(rule["shadow_opacity"])
            canv.setFillColor(colors.HexColor(rule["shadow_color"]))
            # Diffused shadow: stacked translucent rects, widest first.
            layers, blur = int(rule["shadow_layers"]), rule["shadow_blur_pt"]
            alpha = rule["shadow_opacity"] / layers
            if hasattr(canv, "setFillAlpha"):
                canv.setFillAlpha(alpha)
            for i in range(layers):
                grow = blur * (layers - i) / layers
                canv.roundRect(x + rule["shadow_offset_x_pt"] - grow,
                               y + rule["shadow_offset_y_pt"] - grow,
                               self._width + 2 * grow, self._height + 2 * grow,
                               grow, stroke=0, fill=1)
            if hasattr(canv, "setFillAlpha"):
                canv.setFillAlpha(1)
            canv.setFillColor(colors.white)
            canv.rect(x, y, self._width, self._height, stroke=0, fill=1)
        finally:
            canv.restoreState()
        return super().drawOn(canv, x, y, _sW=_sW)


class GlobalReportTable(ReliefTableMixin, __import__("reportlab.platypus", fromlist=["Table"]).Table):
    """Canonical ReportLab table: shared vector shadow and global border policy.

    Existing semantic TableStyle can still customize content and headers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from reportlab.platypus import TableStyle
        self.setStyle(TableStyle(table_relief_commands()))


def legal_qr_table_style(*, inner=False):
    """One authoritative layout for legal QR tables: style/30_tables.js.

    These are container tables, not FILE INFORMATION data tables.
    """
    from reportlab.platypus import TableStyle
    cfg = _STYLE["LEGAL_QR_TABLE_LAYOUT"]
    spec = cfg["qr_inner" if inner else "outer"]
    cmds = [("VALIGN", (0, 0), (-1, -1), spec["vertical_alignment"])]
    if inner:
        cmds.append(("ALIGN", (0, 0), (-1, -1), spec["horizontal_alignment"]))
    for side in ("LEFT", "RIGHT", "TOP", "BOTTOM"):
        cmds.append((side + "PADDING", (0, 0), (-1, -1), spec["padding_pt"]))
    if not inner:
        cmds.append(("RIGHTPADDING", (0, 0), (0, 0), BRIDGE_LAYOUT["legal_qr"]["cell_right_padding_pt"]))
    return TableStyle(cmds)


def global_table_profile():
    return _STYLE["GLOBAL_TABLE_PROFILE"]


def globalize_table(table, header=True, alignments=None):
    """Give any data table the one global presentation (header, stripes, rules, frame, shadow).

    alignments: key of TABLE_COLUMN_ALIGNMENTS for per-column body alignment.
    """
    from reportlab.platypus import TableStyle
    if not isinstance(table, GlobalReportTable):
        table.__class__ = type("Global" + type(table).__name__, (ReliefTableMixin, type(table)), {})
    # Drop legacy per-generator lines/backgrounds so every table is identical.
    table._linecmds = []
    table._bkgrndcmds = []
    table.setStyle(reportlab_table_style(header=header))
    if alignments:
        first = 1 if header else 0
        for column, align in _STYLE["TABLE_COLUMN_ALIGNMENTS"][alignments].items():
            table.setStyle(TableStyle([("ALIGN", (int(column), first), (int(column), -1), align)]))
    return table


def table_relief_commands():
    """Central asymmetric 3D border; drawn as real vector strokes."""
    from reportlab.lib import colors
    rule = TABLE_RELIEF
    edge = colors.HexColor(rule["edge_color"])
    return [("BOX", (0, 0), (-1, -1), rule["frame_pt"], edge)]


def combined_table_style():
    """Exact legacy combined-table presentation, now declarative in 30_tables.js."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    rule = _STYLE["TABLE_PRESENTATION_VARIANTS"]["combined"]
    return TableStyle([
        ("BACKGROUND", (0,0),(-1,0), colors.HexColor(rule["header_background"])),
        ("TEXTCOLOR", (0,0),(-1,0), colors.HexColor(rule["header_text_color"])),
        ("VALIGN", (0,0),(-1,-1), rule["vertical_alignment"]),
        ("ALIGN", (0,0),(-1,0), rule["header_alignment"]),
        ("ALIGN", (0,1),(0,-1), rule["first_column_alignment"]),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.HexColor(v) for v in rule["body_backgrounds"]]),
        ("LINEBELOW", (0,0),(-1,-1), rule["row_line_width_pt"], colors.HexColor(rule["row_line_color"])),
        ("TOPPADDING", (0,0),(-1,-1), rule["cell_padding_pt"]),
        ("BOTTOMPADDING", (0,0),(-1,-1), rule["cell_padding_pt"]),
        ("LEFTPADDING", (0,0),(-1,-1), rule["cell_padding_pt"]),
        ("RIGHTPADDING", (0,0),(-1,-1), rule["cell_padding_pt"]),
        ("BOTTOMPADDING", (0,0),(-1,0), rule["header_bottom_padding_pt"]),
    ] + table_relief_commands())


def aligned_fields_table_style():
    """Original aligned-fields TableStyle, without local presentation literals."""
    from reportlab.platypus import TableStyle
    rule = _STYLE["TABLE_PRESENTATION_VARIANTS"]["aligned_fields"]
    return TableStyle([
        ("VALIGN", (0,0),(-1,-1), rule["vertical_alignment"]),
        ("LEFTPADDING", (0,0),(-1,-1), rule["left_padding_pt"]),
        ("RIGHTPADDING", (0,0),(-1,-1), rule["right_padding_pt"]),
        ("TOPPADDING", (0,0),(-1,-1), rule["top_padding_pt"]),
        ("BOTTOMPADDING", (0,0),(-1,-1), rule["bottom_padding_pt"]),
    ])


def combined_column_widths(total_width):
    return [total_width * v for v in COLUMNS["combined"].values()]


# Universal ReportLab table styling. All variants use the same central palette,
# spacing, borders and typography. The variant changes only semantic emphasis.
def reportlab_table_style(variant="standard", header=True):
    """Single canonical FILE INFORMATION presentation from style/30_tables.js."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    if variant not in {"standard", "explanatory", "ots", "combined", "hashes", "certificate", "timestamp"}:
        raise ValueError(f"Unknown table variant: {variant}")
    profile = global_table_profile()
    pad = profile["cell_padding_pt"]
    commands = [
        ("VALIGN", (0,0),(-1,-1),profile["body_valign"]),
        ("ALIGN", (0,0),(-1,-1),profile["body_align"]),
        ("ROWBACKGROUNDS", (0,1) if header else (0,0),(-1,-1),
         [colors.HexColor(profile["body_background"]), colors.HexColor(profile["stripe_background"])]),
        ("LINEBELOW", (0,0),(-1,-1),profile["row_rule_pt"],colors.HexColor(TABLE_RELIEF["row_rule_color"])),
    ]
    for side in ("TOP", "BOTTOM", "LEFT", "RIGHT"):
        commands.append((side+"PADDING",(0,0),(-1,-1),pad))
    if header:
        commands.extend([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor(profile["header_background"])),
            ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor(profile["header_text_color"])),
            ("FONTNAME",(0,0),(-1,0),font_name(profile["header_font_role"])),
            ("FONTSIZE",(0,0),(-1,0),FONTS["table_header"]),
            ("ALIGN",(0,0),(-1,0),profile["header_align"]),
            ("BOTTOMPADDING",(0,0),(-1,0),TABLE["header_bottom_padding_pt"]),
        ])
    return TableStyle(commands + table_relief_commands())


def timestamp_table_style(*, compact=False, row_count=0):
    """Canonical timestamp presentation: no local ReportLab style constants."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    profile = global_table_profile()
    pad = profile["compact_padding_pt"] if compact else profile["cell_padding_pt"]
    vertical = profile["compact_vertical_padding_pt"]
    commands = [
        ("VALIGN", (0, 0), (-1, -1), profile["timestamp_valign"]),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [
            colors.HexColor(profile["body_background"]),
            colors.HexColor(profile["stripe_background"])]),
    ]
    for side in ("LEFT", "RIGHT"):
        commands.append((side + "PADDING", (0, 0), (-1, -1), pad))
    for side in ("TOP", "BOTTOM"):
        commands.append((side + "PADDING", (0, 0), (-1, -1), vertical))
    if row_count > 1 and profile["timestamp_compact_row_separator"]:
        commands.append(("LINEBELOW", (0, 0), (-1, -2), profile["row_rule_pt"],
                         colors.HexColor(profile["stripe_background"])))
    return TableStyle(commands + table_relief_commands())


def normalize_table_header_paragraphs(table):
    """Apply actual white text to Paragraph cells (TableStyle alone cannot)."""
    from reportlab.platypus import Paragraph
    from reportlab.lib import colors
    from copy import copy
    if not table._cellvalues:
        return table
    for i, cell in enumerate(table._cellvalues[0]):
        if isinstance(cell, Paragraph):
            style = copy(cell.style)
            style.textColor = colors.HexColor(global_table_profile()["header_text_color"])
            style.fontName = font_name("bold")
            style.fontSize = FONTS["table_header"]
            table._cellvalues[0][i] = Paragraph(cell.text, style)
    return table


# Shared title and legal-panel styling for all ReportLab report modes.
# This centralizes styling only; it does not change report data or signatures.
def report_title_flowables(width_pt):
    from reportlab.platypus import Paragraph, TableStyle, Spacer
    Table = GlobalReportTable
    from reportlab.lib import colors
    items = [
        Paragraph("CRYPTO REPORT ENTERPRICE / TECHNISCHER PRÜFBERICHT", heading_style("h2")),
        Paragraph("SHA-256 Hash Report", heading_style("h1")),
        Paragraph("Kryptographischer Existenznachweis", heading_style("h3")),
    ]
    bar = Table([[""]], colWidths=[width_pt], rowHeights=[_STYLE["CENTRAL_LAYOUT"]["title"]["separator_height_pt"]])
    bar.setStyle(title_separator_table_style())
    items.extend([bar, Spacer(1, _central_visual('pdf_object_rules__L311__height'))])
    return items


def legal_qr_box_style():
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    return TableStyle([
        ("BOX",(0,0),(-1,-1),_central_visual('pdf_object_rules__L321__table_BOX_3'),colors.HexColor(COLORS["accent"])),
        ("LINEBELOW",(0,0),(0,0),_central_visual('pdf_object_rules__L322__table_LINEBELOW_3'),colors.HexColor(COLORS["grid"])),
        ("BACKGROUND",(0,1),(0,1),colors.HexColor(COLORS["stripe"])),
        ("ALIGN",(0,0),(-1,-1),_central_visual('pdf_object_rules__L324__table_ALIGN_3')),
        ("LEFTPADDING",(0,0),(-1,-1),_central_visual('pdf_object_rules__L325__table_LEFTPADDING_3')),("RIGHTPADDING",(0,0),(-1,-1),_central_visual('pdf_object_rules__L325__table_RIGHTPADDING_3')),
        ("TOPPADDING",(0,0),(0,0),_central_visual('pdf_object_rules__L326__table_TOPPADDING_3')),("BOTTOMPADDING",(0,0),(0,0),_central_visual('pdf_object_rules__L326__table_BOTTOMPADDING_3')),
        ("TOPPADDING",(0,1),(0,1),_central_visual('pdf_object_rules__L327__table_TOPPADDING_3')),("BOTTOMPADDING",(0,1),(0,1),_central_visual('pdf_object_rules__L327__table_BOTTOMPADDING_3'))])


def legal_qr_layout_style():
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    pad = LEGAL_CONTAINER["padding_pt"]
    return TableStyle([
        ("VALIGN",(0,0),(-1,-1),_central_visual('pdf_object_rules__L335__table_VALIGN_3')),
        ("BACKGROUND",(0,0),(0,0),colors.HexColor(LEGAL_CONTAINER["background"])),
        ("LINEBELOW",(0,0),(0,0),_central_visual('pdf_object_rules__L337__table_LINEBELOW_3'),colors.HexColor(COLORS["grid"])),
        ("LEFTPADDING",(0,0),(0,0),pad),("RIGHTPADDING",(0,0),(0,0),pad),
        ("TOPPADDING",(0,0),(0,0),pad),("BOTTOMPADDING",(0,0),(0,0),pad),
        ("LEFTPADDING",(1,0),(1,0),_central_visual('pdf_object_rules__L340__table_LEFTPADDING_3')),("RIGHTPADDING",(1,0),(1,0),_central_visual('pdf_object_rules__L340__table_RIGHTPADDING_3'))])


def legal_panel_table_style():
    """Exact legacy legal panel presentation, now owned by the JS style loader."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    spec = _STYLE["CENTRAL_BLOCK_TABLE_STYLES"]["legal_panel"]
    whole = (0, 0), (-1, -1)
    return TableStyle([
        ("BACKGROUND", *whole, colors.HexColor(LEGAL_CONTAINER["background"])),
        ("BOX", *whole, spec["box_width_pt"], colors.HexColor(LEGAL_CONTAINER["border_color"])),
        *[(name, *whole, LEGAL_CONTAINER["padding_pt"]) for name in spec["padding_commands"]],
    ])


def title_separator_table_style():
    """Exact legacy heading separator presentation, loaded exclusively from JS."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    spec = _STYLE["CENTRAL_BLOCK_TABLE_STYLES"]["title_separator"]
    whole = (0, 0), (-1, -1)
    return TableStyle([
        ("BACKGROUND", *whole, colors.HexColor(COLORS["accent"])),
        *[(name, *whole, spec["padding_pt"][name]) for name in spec["padding_commands"]],
    ])


def volume_block_table_style():
    """One authoritative JS definition for VOLUME table geometry and decoration."""
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    block = _STYLE["INFORMATION_BLOCK_STYLE"]
    geo = block["volume_row_geometry"]
    return TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor(block["background"])),
        ("LINEBEFORE",(0,0),(0,-1),block["border_left_pt"],colors.HexColor(block["border_color"])),
        ("LINEBELOW",(0,-1),(-1,-1),block["border_bottom_pt"],colors.HexColor(block["separator_color"])),
        ("LEFTPADDING",(0,0),(-1,-1),geo["horizontal_padding_pt"]),
        ("RIGHTPADDING",(0,0),(-1,-1),geo["horizontal_padding_pt"]),
        ("TOPPADDING",(0,0),(-1,-1),geo["top_padding_pt"]),
        ("BOTTOMPADDING",(0,0),(-1,-1),geo["bottom_padding_pt"]),
        ("TOPPADDING",(0,0),(-1,0),geo["first_row_top_padding_pt"]),
        ("BOTTOMPADDING",(0,-1),(-1,-1),geo["last_row_bottom_padding_pt"]),
    ])


def timestamp_cell_paragraph_style(role, *, parent, font_size_pt, leading_pt):
    """Centralized timestamp cell typography; font metrics are inherited inputs."""
    from reportlab.lib.styles import ParagraphStyle
    spec = _STYLE['TIMESTAMP_CELL_TYPOGRAPHY'][role]
    kwargs = dict(parent=parent, fontSize=font_size_pt, leading=leading_pt,
                  wordWrap=spec['word_wrap'], splitLongWords=spec['split_long_words'],
                  spaceBefore=spec['space_before_pt'], spaceAfter=spec['space_after_pt'])
    if 'font_name' in spec:
        kwargs['fontName'] = unicode_font(spec['font_name'])
    return ParagraphStyle('AlignedKVLabelV231' if role == 'label' else 'AlignedKVValueV231', **kwargs)


def combined_cell_paragraph_styles(base_styles, constants):
    """Centralized combined-report cell presentation; no data or crypto logic."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.lib import colors
    policy = _STYLE['COMBINED_CELL_TYPOGRAPHY']
    output = {}
    for role in ('safe', 'hash', 'header'):
        spec = policy[role]
        kwargs = dict(parent=base_styles[spec['parent_key']],
                      fontSize=getattr(constants, spec['font_size_constant']),
                      alignment={'LEFT': TA_LEFT, 'CENTER': TA_CENTER}[spec['alignment']])
        if 'wrap_key' in spec:
            kwargs['wordWrap'] = _central_visual(spec['wrap_key'])
        if 'leading_constant' in spec:
            kwargs['leading'] = getattr(constants, spec['leading_constant'])
        else:
            kwargs['leading'] = max(kwargs['fontSize'] * spec['leading_multiplier'], spec['minimum_leading_pt'])
        if 'text_color' in spec:
            kwargs['textColor'] = colors.HexColor(spec['text_color'])
        output[role] = ParagraphStyle(spec['name'], **kwargs)
    return output


def apply_profile_presentation(styles, profile, *, rules=None):
    """Apply a JS profile atomically after validating every required input.

    A missing/invalid rule must not leave some production ParagraphStyles
    mutated while other styles still contain their original settings.
    """
    from reportlab.lib import colors as rl_colors
    from math import isfinite

    source = _STYLE if rules is None else rules
    if profile not in ("SINGLE", "COMBINED"):
        raise ValueError(f"Unsupported report presentation profile: {profile}")
    config = source[f"{profile}_PRESENTATION"]
    required = ("title_style", "header_style", "legal_style")
    for key in required:
        if key not in styles:
            raise KeyError(f"Missing required ReportLab style: {key}")
    # Resolve all values before modifying any object.
    title_color = rl_colors.HexColor(config["title_color"])
    header_color = rl_colors.HexColor(config["header_color"])
    legal_color = rl_colors.HexColor(config["legal_color"])
    title_size = config["title_font_pt"]
    title_leading = config["title_leading_pt"]
    alignment = config["title_alignment"]
    legal_size = source["FONTS"]["legal"]
    for label, value in (("title_font_pt", title_size),
                         ("title_leading_pt", title_leading),
                         ("legal font", legal_size)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"Invalid positive PDF metric {label}: {value!r}")
    if isinstance(alignment, bool) or not isinstance(alignment, int) or alignment not in (0, 1, 2, 4):
        raise ValueError(f"Invalid title alignment: {alignment!r}")
    title = styles["title_style"]
    title.textColor = title_color
    title.fontSize = title_size
    title.leading = title_leading
    title.alignment = alignment
    styles["header_style"].textColor = header_color
    legal = styles["legal_style"]
    legal.textColor = legal_color
    legal.fontSize = legal_size
    legal.leading = legal_size + 2
    return styles
