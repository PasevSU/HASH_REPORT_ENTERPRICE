"""Reorganized PDF layout helpers for the bridge.

Order:
    1. Title
    2. Legal basis + QR code (right aligned)
    3. Report ID + Report Type (centered)
    4. START ISSUER (identification only)
    5. System Info + hashes right after Hardware ID
    6. Evidence table
    7. STOP ISSUER (identification only)
    8. TIMESTAMP TOTAL (protocol summary + full details)
    9. Legal declaration + signature
   10. Embedded attachments list

Visual conventions:
    * Legal text is 8pt, color #3a3a3a (soft black).
    * Normal body text is 9pt, color #1a1a1a.
    * Section headings are 12pt, color #2c3e50.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image

from hash_report_core import ReportConstants
from pdf_object_rules import BRIDGE_LAYOUT, page_geometry, display_hash, bridge_paragraph_style


def _legal_qr_widths():
    """Return the centrally configured legal-text and QR column widths."""
    body_width = page_geometry()["body_width_pt"]
    qr_fraction = BRIDGE_LAYOUT["legal_qr"]["qr_column_fraction"]
    qr_width = body_width * qr_fraction
    return body_width - qr_width, qr_width


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
QR_TARGET_URL = BRIDGE_LAYOUT["qr_target_url"]
QR_CAPTION = BRIDGE_LAYOUT["qr_caption_text"]


# ---------------------------------------------------------------------------
# 2. Legal basis (left text + right QR code)
# ---------------------------------------------------------------------------

def _generate_qr_image(url: str, size_mm: float = 28):
    """Return a ReportLab Image of a QR code pointing to `url`.

    Falls back to a plain text placeholder if `qrcode` is unavailable.
    """
    try:
        import qrcode  # type: ignore
    except ImportError:
        fallback_style = bridge_paragraph_style("QRFallback", "qr_fallback", alignment=TA_CENTER)
        return Paragraph(
            f"<i>[QR unavailable]<br/>{url}</i>",
            fallback_style,
        )

    try:
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        fallback_style = bridge_paragraph_style("QRFallback2", "qr_fallback", alignment=TA_CENTER)
        return Paragraph(f"<i>{url}</i>", fallback_style)


def build_legal_basis(story, styles):
    """Legal note on the left, QR code to legislation on the right."""
    legal_style = bridge_paragraph_style("LegalBasisText", "legal", styles["normal_style"], TA_LEFT)
    caption_style = bridge_paragraph_style("QRCaption", "qr_caption", styles["normal_style"], TA_CENTER)

    legal_text = (
        "<b>Rechtliche und technische Hinweise für Deutschland</b><br/>"
        "Dieser Bericht dokumentiert die kryptographische Identifikation und "
        "Integritätsprüfung der bezeichneten elektronischen Dateien sowie "
        "&mdash; bei erfolgreicher RFC-3161-Verifikation &mdash; deren "
        "zeitliche Bindung.<br/><br/>"
        "<b>§ 371 ZPO:</b> Ist eine elektronische Datei Gegenstand des "
        "Beweises, erfolgt der Beweisantritt durch Vorlegung oder "
        "Übermittlung der Datei.<br/>"
        "<b>§ 286 ZPO:</b> Das Gericht entscheidet über die Beweiskraft "
        "nach freier Überzeugung.<br/>"
        "<b>Art. 41 Abs. 1 eIDAS-VO (EU) Nr. 910/2014:</b> Elektronischen "
        "Zeitstempeln darf die Rechtswirkung oder Zulässigkeit als "
        "Beweismittel nicht allein wegen ihrer elektronischen Form oder "
        "fehlenden Qualifikation abgesprochen werden.<br/><br/>"
        "<b>Technische Grundlage:</b> SHA-256 identifiziert reproduzierbar "
        "die geprüfte Bytefolge; ein verifizierter RFC-3161-Zeitstempel "
        "bindet deren Message Imprint an die vom Zeitstempeldienst "
        "bestätigte Zeit."
    )

    qr_image = _generate_qr_image(QR_TARGET_URL, size_mm=BRIDGE_LAYOUT["legal_qr"]["qr_size_mm"])

    # Two-column table: legal text (left, wide), QR + caption (right, narrow)
    qr_cell = Table(
        [[qr_image], [Paragraph(QR_CAPTION.replace("\n", "<br/>"), caption_style)]],
        colWidths=[BRIDGE_LAYOUT["qr_cell_width_mm"] * mm],
    )
    qr_cell.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    data = [[Paragraph(legal_text, legal_style), qr_cell]]
    table = Table(data, colWidths=[w * mm for w in BRIDGE_LAYOUT["legal_table_widths_mm"]])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), BRIDGE_LAYOUT["legal_qr"]["cell_right_padding_pt"]),
        ("LEFTPADDING", (1, 0), (1, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(table)
    story.append(Spacer(1, ReportConstants.SPACER_LEGAL))


# ---------------------------------------------------------------------------
# 3. Report ID / Type centered
# ---------------------------------------------------------------------------

def build_header_identity(story, styles, report_id, report_type):
    center_style = bridge_paragraph_style("HeaderCenter", "header_identity", styles["normal_style"], TA_CENTER)
    story.append(Paragraph(f"<b>Report ID:</b> {report_id}", center_style))
    story.append(Paragraph(f"<b>Report Type:</b> {report_type}", center_style))
    story.append(Spacer(1, BRIDGE_LAYOUT["header_identity"]["trailing_spacer_pt"]))


# ---------------------------------------------------------------------------
# 4 + 7. Compact TSA ISSUER blocks
# ---------------------------------------------------------------------------

_ISSUER_IDENT_KEYS = {
    "Selected TSA",
    "TSA Endpoint",
    "Failover Position",
    "Local Request Start",
    "Local Response Received",
    "TSA Round-Trip Duration",
    "Status",
    "Status Description",
    "Timestamp (genTime, exactly as issued by TSA)",
    "TSA Serial Number",
    "TSA Policy OID",
    "Nonce (returned and verified)",
    "TimeStampToken SHA-256",
    "Embedded RFC 3161 Response File",
    "Embedded Response Size",
    "Embedded Response SHA-256",
    "TSA Signer Certificate",
    "TSA Signer SHA-256",
    "TSA Signer Issuer",
    "TSA Signer EKU Time Stamping",
    "TSA Signer Valid at genTime",
    "Root CA SHA-256",
    "Root Trust Anchor Check",
}


def build_tsa_issuer_block(story, styles, marker_label, timestamp_text,
                            generator):
    heading_style = bridge_paragraph_style(
        f"TsaBlockHeading_{marker_label}", "tsa_heading", styles["normal_style"])
    heading_style.keepWithNext = True
    story.append(Paragraph(
        f"<b>Cryptographic Timestamp RFC 3161/5816 — "
        f"{marker_label} ISSUER:</b>",
        heading_style,
    ))

    _, rows = generator._timestamp_text_to_rows(
        timestamp_text, signature_only=False,
    )
    filtered = [(k, v) for (k, v) in rows if k in _ISSUER_IDENT_KEYS]
    if filtered:
        generator._add_aligned_key_value_table(story, filtered, styles)
    story.append(Spacer(1, ReportConstants.SPACER_LEGAL))


# ---------------------------------------------------------------------------
# 8. TIMESTAMP TOTAL
# ---------------------------------------------------------------------------

def build_timestamp_total(story, styles, generator,
                           start_text, stop_text,
                           evidence_sha256, end_imprint,
                           start_anchor_type, duration_ms):
    heading_style = bridge_paragraph_style("TimestampTotalHeading", "total_heading", styles["normal_style"])
    sub_style = bridge_paragraph_style("TimestampTotalSub", "total_sub", styles["normal_style"])
    story.append(Paragraph("<b>TIMESTAMP TOTAL</b>", heading_style))

    # 8a. Protocol Summary (once)
    story.append(Paragraph("<b>Protocol Summary</b>", sub_style))
    common_rows = [
        ("Protocol", "RFC 3161 / RFC 5816 Time-Stamp Protocol"),
        ("Evidence Digest Algorithm", "SHA-256 (evidence hash; inspect each signed TSA token for its imprint algorithm)"),
        ("Token Format", "CMS / SignedData"),
        ("Timestamp Structure", "START signature + STOP signature"),
        ("START Binding", "SHA-256 of the evidence file"),
        ("STOP Binding",
         "SHA-256 closing digest linking the evidence SHA-256, "
         "START TimeStampToken SHA-256 and Report ID"),
        ("TSA Selection",
         "Primary + 3 alternatives (DFN, DigiCert, GlobalSign, Sectigo) "
         "with automatic failover"),
        ("Token Verification", "Message Imprint + Nonce + CMS signature"),
        ("Signer Validation",
         "TSA signer certificate, critical Time Stamping EKU, validity at "
         "genTime and X.509 certificate chain"),
        ("Revocation Validation",
         "CRL and OCSP when available; unavailable network validation is "
         "reported explicitly"),
        ("genTime Precision",
         "Preserved exactly as signed by the TSA; fractional precision is "
         "shown only when present in the token"),
        ("Evidence Preservation",
         "Original TimeStampResp and captured certificate/revocation "
         "artifacts are embedded as binary PDF attachments"),
        ("Qualification Status",
         "RFC 3161 alone is not presented as proof of a qualified "
         "electronic time stamp"),
        ("Local Timing Status",
         "Local request/response times and Processing Duration are "
         "informational measurements, not TSA-certified time evidence"),
    ]
    generator._add_aligned_key_value_table(
        story, common_rows, styles, label_ratio=0.30, compact=True,
    )
    story.append(Spacer(1, ReportConstants.SPACER_LEGAL))

    # 8b. Full START details
    story.append(Paragraph(
        "<b>Full START Timestamp Details</b>", sub_style,
    ))
    _, start_rows = generator._timestamp_text_to_rows(
        start_text, signature_only=False,
    )
    if start_rows:
        generator._add_aligned_key_value_table(story, start_rows, styles)
    story.append(Spacer(1, ReportConstants.SPACER_LEGAL))

    # 8c. Closing-link facts + full STOP details
    story.append(Paragraph(
        "<b>Full STOP Timestamp Details</b>", sub_style,
    ))
    closing_rows = [
        ("Evidence-set SHA-256", evidence_sha256),
        ("STOP Closing Message Imprint", end_imprint),
        ("START Anchor Used by STOP",
         start_anchor_type.replace("END", "STOP")),
    ]
    generator._add_aligned_key_value_table(story, closing_rows, styles)
    story.append(Spacer(1, ReportConstants.SPACER_TIGHT))
    _, stop_rows = generator._timestamp_text_to_rows(
        stop_text, signature_only=False,
    )
    if stop_rows:
        generator._add_aligned_key_value_table(story, stop_rows, styles)
    story.append(Spacer(1, BRIDGE_LAYOUT["spacing"]["stop_details_after_pt"]))

    # 8d. Processing duration
    duration_rows = [
        ("Processing Duration", f"{duration_ms:.3f} ms"),
        ("Processing Duration Explanation",
         "Local elapsed time measured with a monotonic high-resolution "
         "timer from immediately before the START TSA request until "
         "completion of the STOP TSA request and validation. It is "
         "informational, is not TSA-certified, and does not include final "
         "PDF serialization or attachment embedding."),
    ]
    generator._add_aligned_key_value_table(
        story, duration_rows, styles, label_ratio=0.30, compact=True,
    )
    story.append(Spacer(1, BRIDGE_LAYOUT["spacing"]["processing_duration_after_pt"]))


# ---------------------------------------------------------------------------
# 10. Embedded attachments list (bullet-list, no Table)
# ---------------------------------------------------------------------------

def build_embedded_attachments_list(story, styles, attachments):
    heading_style = bridge_paragraph_style("AttachmentsHeading", "attachments_heading", styles["normal_style"])
    story.append(Paragraph(
        "<b>Embedded Evidence Attachments (in this PDF):</b>",
        heading_style,
    ))
    story.append(Paragraph(
        "The following files are embedded byte-for-byte as binary PDF "
        "attachments. Their SHA-256 hashes below can be verified by "
        "extracting the attachments and re-hashing the bytes.",
        styles["small_style"],
    ))
    story.append(Spacer(1, BRIDGE_LAYOUT["spacing"]["attachments_intro_after_pt"]))

    if not attachments:
        story.append(Paragraph(
            "<i>No attachments were embedded.</i>", styles["small_style"],
        ))
        return

    item_style = bridge_paragraph_style("AttachItem", "attachment_item", styles["normal_style"])
    hash_style = bridge_paragraph_style("AttachHashLine", "attachment_hash", styles["normal_style"])

    for i, att in enumerate(attachments, 1):
        size_kb = att.get("size", 0) / 1024.0
        marker = att.get("marker") or "—"
        fname = att.get("filename") or "(unknown)"
        story.append(Paragraph(
            f"<b>{i}.</b> [{marker}] <b>{fname}</b> "
            f"({size_kb:.3f} KB)",
            item_style,
        ))
        story.append(Paragraph(
            f"SHA-256: {display_hash(att.get('sha256')) if att.get('sha256') else 'N/A'}",
            hash_style,
        ))
    story.append(Spacer(1, BRIDGE_LAYOUT["spacing"]["attachments_list_after_pt"]))