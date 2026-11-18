"""Shared branded report header and legal/QR panel; all values come from style/73_report_header.js."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle
from hash_report_generator.pdf_object_rules import _STYLE, font_name


def header_rules():
    return _STYLE["REPORT_HEADER"]


def apply_header_palette(styles):
    """Apply the central title/legal palette to a core style dictionary."""
    rule = header_rules()
    title = styles["title_style"]
    title.textColor = colors.HexColor(rule["title_color"])
    title.fontSize = rule["title_font_size_pt"]
    title.leading = rule["title_leading_pt"]
    title.alignment = rule["title_alignment"]
    styles["header_style"].textColor = colors.HexColor(rule["header_text_color"])
    styles["legal_style"].textColor = colors.HexColor(rule["legal_text_color"])


def _muted(text, rule, bold=False):
    inner = f"<b>{text}</b>" if bold else text
    return f'<font color="{rule["muted_color"]}" size="{rule["muted_font_size_pt"]}">{inner}</font>'


def build_report_header(doc_width, styles, spacers):
    """Return the flowables for title block, rule and legal panel.

    spacers: mapping with keys section, title and legal (points).
    """
    rule = header_rules()
    story = [
        Paragraph(_muted(rule["eyebrow"], rule, bold=True), styles["normal_style"]),
        Spacer(1, spacers["section"]),
        Paragraph(rule["title"], styles["title_style"]),
        Paragraph(_muted(rule["subtitle"], rule), styles["normal_style"]),
        Spacer(1, spacers["section"]),
    ]
    bar = Table([[""]], colWidths=[doc_width], rowHeights=[rule["rule_height_pt"]])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(rule["rule_color"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [bar, Spacer(1, spacers["title"])]

    overview = Paragraph("<br/>".join(rule["legal_html"]), styles["legal_style"])
    qr_path = Path(__file__).resolve().parent / rule["qr_file"]
    if not qr_path.is_file():
        raise FileNotFoundError(f"Mandatory legal QR missing: {qr_path}")
    qr = Image(str(qr_path), width=rule["qr_size_pt"], height=rule["qr_size_pt"])
    qr.hAlign = "CENTER"
    column = rule["qr_column_pt"]
    box = Table([[qr], [Paragraph(rule["qr_caption"], styles["legal_style"])]],
                colWidths=[column], hAlign="RIGHT")
    pad, cap = rule["qr_padding_pt"], rule["qr_caption_padding_pt"]
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), rule["qr_box_pt"], colors.HexColor(rule["qr_box_color"])),
        ("LINEBELOW", (0, 0), (0, 0), rule["qr_divider_pt"], colors.HexColor(rule["qr_divider_color"])),
        ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(rule["qr_caption_background"])),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (0, 0), pad), ("BOTTOMPADDING", (0, 0), (0, 0), pad),
        ("TOPPADDING", (0, 1), (0, 1), cap), ("BOTTOMPADDING", (0, 1), (0, 1), cap),
    ]))
    panel = Table([[overview, box]], colWidths=[doc_width - column, column], hAlign="LEFT")
    panel.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(rule["legal_background"])),
        ("LINEBELOW", (0, 0), (0, 0), rule["legal_rule_pt"], colors.HexColor(rule["legal_rule_color"])),
        ("LEFTPADDING", (0, 0), (0, 0), rule["legal_text_left_padding_pt"]), ("RIGHTPADDING", (0, 0), (0, 0), rule["legal_text_right_padding_pt"]),
        ("LEFTPADDING", (1, 0), (1, 0), rule["qr_left_padding_pt"]), ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (1, 0), (1, 0), 0), ("BOTTOMPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (0, 0), rule["legal_text_vertical_padding_pt"]),
        ("BOTTOMPADDING", (0, 0), (0, 0), rule["legal_text_vertical_padding_pt"]),
    ]))
    story += [panel, Spacer(1, spacers["legal"])]
    return story


def section_heading(text):
    """Uniform section heading with a hairline rule; text is a plain label (colon optional)."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import HRFlowable
    rule = _STYLE["SECTION_HEADING"]
    style = ParagraphStyle(
        "CentralSectionHeading", fontName=font_name("bold"), fontSize=rule["font_size_pt"],
        leading=rule["leading_pt"], textColor=colors.HexColor(rule["color"]),
        spaceBefore=rule["space_before_pt"], spaceAfter=rule["rule_gap_pt"], keepWithNext=1,
    )
    line = HRFlowable(width="100%", thickness=rule["rule_pt"], color=colors.HexColor(rule["rule_color"]),
                      spaceBefore=0, spaceAfter=rule["space_after_pt"])
    return [Paragraph(text.rstrip(":"), style), line]


def info_line(label, value):
    """One uniform 'Label: value' line."""
    from reportlab.lib.styles import ParagraphStyle
    rule = _STYLE["INFO_LINE"]
    style = ParagraphStyle(
        "CentralInfoLine", fontName=font_name(), fontSize=rule["font_size_pt"], leading=rule["leading_pt"],
        textColor=colors.HexColor(rule["value_color"]), spaceAfter=rule["space_after_pt"],
    )
    return Paragraph(f'<font color="{rule["label_color"]}"><b>{label}:</b></font> {value}', style)
