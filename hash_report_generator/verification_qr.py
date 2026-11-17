"""Closing verification block: a QR code that leads to the electronic documents.

The report is sealed twice (embedded RFC 3161 responses and, optionally, the final
PDF signature), but a reader holding only the printed page still needs a pointer to
where the timestamp evidence lives. This module renders that pointer at the physical
end of the report: QR code plus the explicit explanation of what the accompanying
OpenTimestamps proof is and that the link delivers the report and its verification
files together.

Design rules that this module must not break:

* The block is mandatory, not an option: every report ends with it. ChronoSeal
  generates the target once per report (configured base address plus a random code),
  prints it here and records the same address in the evidence case.
* The block is presentation only. It changes no hash, no timestamp and no
  verification result, so it can never turn a failed case into a passing one.
* Geometry and typography come from the central rule ``VERIFICATION_QR``; no colour
  literal is written here.

The generator runs as a stand-alone script without ChronoSeal imports, so the target
arrives through the environment (``CHRONOSEAL_VERIFICATION_QR_URL``), exactly like the
other generator switches. Without a target the block is skipped silently - only a
direct generator invocation can get there, because the pipeline always supplies one.
"""
import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

ENV_URL = 'CHRONOSEAL_VERIFICATION_QR_URL'
SIDECAR_NAME = 'verification-qr.json'
SCHEMA = 'chronoseal.verification-qr/v1'
ALLOWED_SCHEMES = ('http', 'https')
MAX_URL_LENGTH = 2048


class VerificationQrError(ValueError):
    """The operator supplied a target that must not end up in a sealed report."""


def _rules():
    try:
        from .pdf_object_rules import VERIFICATION_QR, COLORS, font_name, page_geometry
    except ImportError:
        from pdf_object_rules import VERIFICATION_QR, COLORS, font_name, page_geometry
    return VERIFICATION_QR, COLORS, font_name, page_geometry


def normalise(url):
    """Return the canonical target, or ``''`` when nothing was supplied.

    Empty input is only possible for a direct generator run; the pipeline always
    supplies a target because the block is mandatory. Anything that is not an
    absolute http(s) URL raises :class:`VerificationQrError`, because a sealed
    report must not carry a link that cannot resolve.
    """
    text = '' if url is None else str(url).strip()
    if not text:
        return ''
    if len(text) > MAX_URL_LENGTH:
        raise VerificationQrError(f'target URL longer than {MAX_URL_LENGTH} characters')
    if any(character.isspace() for character in text):
        raise VerificationQrError('target URL contains whitespace')
    parts = urlsplit(text)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise VerificationQrError('target URL must use http:// or https://')
    if not parts.netloc:
        raise VerificationQrError('target URL has no host')
    return text


def from_environment(environ=None):
    """Read the generated target from the environment; invalid input raises."""
    source = os.environ if environ is None else environ
    if str(source.get('CHRONOSEAL_VERIFICATION_QR', '')).strip().lower() not in ('1', 'true', 'yes', 'on'):
        return ''
    return normalise(source.get(ENV_URL, ''))


def _electronic_documents_text(url, is_combined):
    """Caption body: German first, then the English rendering."""
    from xml.sax.saxutils import escape
    scope_de = 'mehrere Dateien' if is_combined else 'eine Datei'
    scope_en = 'several files' if is_combined else 'a single file'
    target = escape(url)
    return (
        '<b>Elektronische Dokumente zur Verifikation der Zeitstempel</b><br/>'
        'Der QR-Code führt zu den Unterlagen, mit denen die in diesem Bericht '
        'ausgewiesenen Zeitstempel unabhängig geprüft werden können: '
        'RFC-3161-Zeitstempelantworten (START/STOP), TSA-Zertifikate mit '
        'Vertrauenskette, Sperr- und Statusinformationen (CRL/OCSP) sowie der '
        'OpenTimestamps-Beleg.<br/>'
        '<b>Was der OpenTimestamps-Beleg ist:</b> eine eigene kleine Prüfdatei mit '
        'der Endung <i>.ots</i>, die den SHA-256-Wert genau dieses PDF-Dokuments in '
        'der Bitcoin-Blockchain verankert. Er kann erst nach dem Versiegeln des '
        'Berichts entstehen und wird deshalb getrennt neben dem Bericht aufbewahrt; '
        'er ist kein Anhang im PDF und verändert dessen Bytes nicht. Erst mit ihm '
        'lässt sich unabhängig zeigen, dass dieses Dokument in dieser Form bereits '
        'zu einem bestimmten Zeitpunkt existierte. Der Beleg trägt zunächst eine '
        'offene Kalenderbestätigung und wird nach der Aufnahme in einen '
        'Bitcoin-Block endgültig bestätigt; geprüft wird er mit dem Befehl '
        '<i>ots verify</i>.<br/>'
        f'Dieser Bericht dokumentiert {scope_de}. Der Verweis liefert den Bericht '
        'und die zugehörigen Prüfdateien gemeinsam – je nach Umfang der '
        'Dokumentation als einzelne Datei oder als ZIP-Archiv mit mehreren Dateien. '
        'Der Bericht selbst bleibt unverändert: Hashes, Signaturen und Zeitstempel '
        'werden durch diesen Verweis nicht ersetzt.<br/>'
        '<b>Automated verification reference:</b> the QR code resolves to the '
        'electronic timestamp evidence for the files documented in this report '
        '(RFC 3161 responses, TSA certificates and trust chains, CRL/OCSP status) '
        'together with the OpenTimestamps proof. That proof is a separate small '
        '<i>.ots</i> file anchoring the SHA-256 value of this very PDF in the '
        'Bitcoin blockchain; it can only be created after the report is sealed, so '
        'it is kept next to the report instead of being attached inside it, and it '
        'is what shows independently that this document already existed at a given '
        'time. It starts out with a pending calendar confirmation, is final once a '
        'Bitcoin block confirms it, and is checked with <i>ots verify</i>. This '
        f'report documents {scope_en}; the link delivers the report and its '
        'verification files together, as a single file or as a ZIP archive '
        'depending on what was archived.<br/>'
        f'<b>Ziel / Target:</b> {target}'
    )


def _qr_flowable(url, size_mm):
    """Render the QR code, or return ``None`` when no encoder is available."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Image
    try:
        import qrcode
    except Exception:
        return None
    try:
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        code.add_data(url)
        code.make(fit=True)
        image = code.make_image(fill_color='black', back_color='white')
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        return Image(buffer, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        return None


def build(url, is_combined=True):
    """Return ``(flowables, qr_rendered)`` for one verification target."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    target = normalise(url)
    if not target:
        return [], False
    rules, palette, font_name, page_geometry = _rules()
    body_width = page_geometry()['body_width_pt']
    qr_width = min(rules['qr_column_width_pt'], body_width / 2)
    text_width = max(body_width - qr_width, body_width * 0.4)

    heading = ParagraphStyle(
        'VerificationQrHeading', fontName=font_name('bold'),
        fontSize=rules['heading_font_size_pt'], leading=rules['heading_leading_pt'],
        textColor=colors.HexColor(palette[rules['colors']['heading']]),
        spaceBefore=0, spaceAfter=3)
    body = ParagraphStyle(
        'VerificationQrBody', fontName=font_name('regular'),
        fontSize=rules['body_font_size_pt'], leading=rules['body_leading_pt'],
        textColor=colors.HexColor(palette[rules['colors']['body']]))
    caption = ParagraphStyle(
        'VerificationQrCaption', fontName=font_name('regular'),
        fontSize=rules['caption_font_size_pt'], leading=rules['caption_leading_pt'],
        textColor=colors.HexColor(palette[rules['colors']['caption']]))

    text_cell = [
        Paragraph('Zeitstempel-Verifikation / Timestamp verification', heading),
        Paragraph(_electronic_documents_text(target, is_combined), body),
    ]
    image = _qr_flowable(target, rules['qr_size_mm'])
    rendered = image is not None
    if rendered:
        qr_cell = [image]
    else:
        qr_cell = [
            Paragraph('QR-Code nicht erzeugt / QR code not rendered', caption),
            Spacer(1, 3),
            Paragraph(escape(target), caption),
        ]

    table = Table([[text_cell, qr_cell]], colWidths=[text_width, qr_width])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(palette[rules['colors']['background']])),
        ('BOX', (0, 0), (-1, -1), rules['block_border_pt'],
         colors.HexColor(palette[rules['colors']['border']])),
        ('LEFTPADDING', (0, 0), (-1, -1), rules['block_padding_pt']),
        ('RIGHTPADDING', (0, 0), (-1, -1), rules['block_padding_pt']),
        ('TOPPADDING', (0, 0), (-1, -1), rules['block_padding_pt']),
        ('BOTTOMPADDING', (0, 0), (-1, -1), rules['block_padding_pt']),
    ]))
    flowables = [
        Spacer(1, rules['space_before_pt']),
        KeepTogether([table]),
        Spacer(1, rules['space_after_pt']),
    ]
    return flowables, rendered


def record(url, *, is_combined, qr_rendered, environ=None):
    """Write the sidecar that proves the block really reached the built PDF."""
    source = os.environ if environ is None else environ
    folder = str(source.get('CHRONOSEAL_EVIDENCE_DIR', '') or '').strip()
    if not folder or not url:
        return None
    path = Path(folder).expanduser()
    payload = {
        'schema': SCHEMA,
        'url': url,
        'documented_files': 'multiple' if is_combined else 'single',
        'qr_rendered': bool(qr_rendered),
        'applied_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    try:
        path.mkdir(parents=True, exist_ok=True)
        target = path / SIDECAR_NAME
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(target)
        return target
    except Exception:
        return None


def add_section(story, *, is_combined=True, environ=None):
    """Append the closing block to ``story`` and return the target URL (or ``''``)."""
    url = from_environment(environ)
    if not url:
        return ''
    flowables, rendered = build(url, is_combined=is_combined)
    if not flowables:
        return ''
    story.extend(flowables)
    record(url, is_combined=is_combined, qr_rendered=rendered, environ=environ)
    return url
