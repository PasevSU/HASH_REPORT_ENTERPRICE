"""Shared presentation-only ReportLab table with a central minimum-fragment policy."""
from reportlab.platypus import Table
from .style_runtime import layout_rule

class PolicyTable(Table):
    """Avoid 1–2-row fragments without changing content or table data.

    ReportLab may split the same table multiple times; each split is checked.
    If there is insufficient space for the minimum top fragment, the whole
    table is deferred. A physically oversized single row is not truncated.
    """
    def split(self, availWidth, availHeight):
        minimum = int(layout_rule("document_policy", "minimum_table_fragment_rows"))
        if minimum < 1:
            raise ValueError("minimum_table_fragment_rows must be positive")
        rows = len(self._cellvalues)
        if rows < 2 * minimum:
            return [] if self.wrap(availWidth, availHeight)[1] > availHeight else [self]
        # Reduce the split height until both fragments have at least the
        # required number of data rows (not counting repeated headers).
        trial = availHeight
        for _ in range(rows + 2):
            fragments = super().split(availWidth, trial)
            if not fragments:
                return []
            if len(fragments) < 2:
                return fragments
            first, second = fragments[0], fragments[1]
            repeat = self.repeatRows if isinstance(self.repeatRows, int) else len(self.repeatRows)
            top = len(first._cellvalues) - repeat
            bottom = len(second._cellvalues) - repeat
            if top < minimum:
                return []
            if bottom >= minimum:
                return fragments
            # Move at least one row to the next page, preserving cell content.
            heights = getattr(first, "_rowHeights", None)
            if not heights:
                return []
            trial -= max(float(heights[-1]), 0.5) + 0.1
        return []
