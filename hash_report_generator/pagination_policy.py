"""Shared ReportLab pagination decisions driven by style/90_pagination.js.

No hard-coded CondPageBreak thresholds. Short sections are measured by Platypus
at layout time; oversized tables remain splittable and repeat their headers.
"""
from reportlab.platypus import KeepTogether, Spacer, Table
try:
    from .style_loader import load_styles
except ImportError:
    from style_loader import load_styles


def pagination_config():
    config = load_styles().get("PAGINATION", {})
    if config.get("paper") != "A4":
        raise ValueError("Central pagination requires A4")
    return config


def keep_short_section(heading, table, *, gap_pt=4):
    """Keep heading with table if short; never force a fixed minimum free height."""
    config = pagination_config()
    if not isinstance(table, Table):
        raise TypeError("Expected ReportLab Table")
    if not config.get("short_tables_keep_together", True):
        return [heading, Spacer(1, gap_pt), table]
    max_rows = int(config.get("short_table_max_rows", 8))
    if len(table._cellvalues) <= max_rows:
        return KeepTogether([heading, Spacer(1, gap_pt), table])
    # For long tables caller should add heading and table separately so rows split.
    raise ValueError("Long table must be placed as separate splittable flowables")


def keep_heading_with_first_paragraph(heading, first_paragraph, *, gap_pt=4):
    """Keep a heading with its first actual paragraph, not with a blank spacer.

    ReportLab measures the group and moves it as one flowable when required.
    This deliberately does not lock the rest of the section on one page.
    """
    config = pagination_config()
    if config.get("no_orphan_section_headings", True) and config.get("heading_first_paragraph_keep_together", True):
        return KeepTogether([heading, Spacer(1, gap_pt), first_paragraph])
    return [heading, Spacer(1, gap_pt), first_paragraph]
