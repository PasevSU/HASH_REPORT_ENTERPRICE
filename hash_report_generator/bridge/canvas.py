"""Bridge canvas with page-level identification footer.

Extends ReportLab's Canvas to draw, on every page:
    left   : Report ID + file count
    center : Page X / Y
    right  : Package Total Checksum (short form) + per-page unique ID (PID)

The footer is drawn on top of the existing page-numbering behavior and
produces a distinct, verifiable identifier on every page, similar to the
practice of German authorities (Behördenkennung).

Nothing in hash_report_core is modified; the original NumberedCanvas
remains available for direct CLI usage.
"""
from __future__ import annotations

import hashlib
from functools import partial

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from hash_report_generator.style_loader import load_styles
from hash_report_generator.pdf_object_rules import unicode_font


_BRIDGE_FOOTER = load_styles()["BRIDGE_CANVAS_FOOTER"]


class BridgeNumberedCanvas(canvas.Canvas):
    """Canvas with page numbering and Behördenkennung-style footer."""

    def __init__(self, *args, footer_context=None, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self._footer_context = footer_context or {}

    # ---- ReportLab lifecycle hooks ----
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    # ---- footer drawing ----
    def _draw_footer(self, total_pages):
        page_num = self._pageNumber
        ctx = self._footer_context
        width, _ = self._pagesize

        report_id    = ctx.get("report_id") or ""
        pkg_checksum = ctx.get("package_checksum") or ""
        report_type  = ctx.get("report_type") or ""
        file_count   = ctx.get("file_count")

        # ---- compute per-page unique ID ----
        pid_material = (
            f"{report_id}|{page_num}|{total_pages}|{pkg_checksum}"
        ).encode("utf-8")
        pid = hashlib.sha256(pid_material).hexdigest()[:12]

        # ---- thin separator line above footer ----
        self.setStrokeColorRGB(*_BRIDGE_FOOTER["separator_rgb"])
        self.setLineWidth(_BRIDGE_FOOTER["separator_line_width_pt"])
        self.line(
            _BRIDGE_FOOTER["horizontal_inset_mm"] * mm,
            _BRIDGE_FOOTER["separator_y_pt"],
            width - _BRIDGE_FOOTER["horizontal_inset_mm"] * mm,
            _BRIDGE_FOOTER["separator_y_pt"],
        )

        # ---- LEFT: Report ID + mode + file count ----
        short_type = "Individual" if "Individual" in report_type else "Combined"
        left_bits = [report_id] if report_id else []
        left_bits.append(short_type)
        if file_count is not None:
            left_bits.append(f"files={file_count}")
        left_text = " · ".join(left_bits)

        self.setFont(unicode_font("Helvetica"), _BRIDGE_FOOTER["regular_font_pt"])
        self.setFillColorRGB(*_BRIDGE_FOOTER["regular_rgb"])
        self.drawString(_BRIDGE_FOOTER["horizontal_inset_mm"] * mm, _BRIDGE_FOOTER["baseline_y_pt"], left_text)

        # ---- CENTER: page counter ----
        self.setFont(unicode_font("Helvetica-Bold"), _BRIDGE_FOOTER["bold_font_pt"])
        self.setFillColorRGB(*_BRIDGE_FOOTER["bold_rgb"])
        self.drawCentredString(width / 2, _BRIDGE_FOOTER["baseline_y_pt"], f"Page {page_num} / {total_pages}")

        # ---- RIGHT: PKG short + PID ----
        if pkg_checksum:
            short = f"{pkg_checksum[:10]}…{pkg_checksum[-6:]}"
        else:
            short = "n/a"
        right_text = f"PKG: {short}  ·  PID: {pid}"

        self.setFont(unicode_font("Helvetica"), _BRIDGE_FOOTER["regular_font_pt"])
        self.setFillColorRGB(*_BRIDGE_FOOTER["regular_rgb"])
        self.drawRightString(width - _BRIDGE_FOOTER["horizontal_inset_mm"] * mm, _BRIDGE_FOOTER["baseline_y_pt"], right_text)


def build_canvas_maker(footer_context):
    """Return a callable suitable for SimpleDocTemplate.build(canvasmaker=...).

    ReportLab calls canvasmaker(filename, pagesize=...) internally; using
    functools.partial lets us attach the footer_context without writing a
    wrapper class for every build.
    """
    return partial(BridgeNumberedCanvas, footer_context=footer_context)