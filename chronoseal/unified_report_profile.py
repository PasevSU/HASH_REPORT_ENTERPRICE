"""Shared, versioned visual policy for manual and automation reports.

This module defines the target layout that the audit enforces. It must not drift
away from the engine's own single source of truth
(``hash_report_generator/style/00_page.js`` and ``96_page_identity.js``), so the
gate describes the reports the engine actually produces instead of an
unreachable ideal. ``tests/test_unified_report_profile.py`` enforces that link.

``bottom_mm`` is the audit's body floor (the page margin), not the frame's
reserved bottom: the generator keeps a taller bottom margin and draws the footer
strip inside ``footer_band_mm``, which the audit classifies separately.
"""
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class ReportProfile:
    name: str = 'ChronoSeal Unified A4'
    version: str = '1.0-dev'
    page_width_mm: int = 210
    page_height_mm: int = 297
    left_mm: int = 20
    right_mm: int = 20
    top_mm: int = 20
    bottom_mm: int = 20
    # The footer strip starts at PAGE_IDENTITY.separator_y_pt (65pt = 22.9mm);
    # anything inside it is band content, not body content.
    footer_band_mm: int = 23
    # The checksum appendix sets its title above the body frame
    # (PAGE_IDENTITY.appendix_heading_y_pt); only a page that declares itself an
    # appendix with its canonical title may use this top allowance.
    appendix_top_mm: int = 10
    min_body_words: int = 12

    def audit_options(self):
        return {
            'left_mm': self.left_mm,
            'right_mm': self.right_mm,
            'top_mm': self.top_mm,
            'bottom_mm': self.bottom_mm,
            'footer_band_mm': self.footer_band_mm,
            'appendix_top_mm': self.appendix_top_mm,
            'minimum_body_words': self.min_body_words,
        }

    def to_dict(self):
        return asdict(self)

DEFAULT_PROFILE = ReportProfile()
