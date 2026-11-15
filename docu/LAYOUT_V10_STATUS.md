# DEV v10 — PDF layout rules

- COMBO header Paragraph explicitly uses white text (TableStyle alone cannot override Paragraph textColor).
- Shared table width is 165.5 mm, leaving clearance for ReportLab frame padding on A4 with 20 mm side margins.
- Shared table body background normalized to white; existing zebra row backgrounds remain.
- No change to cryptographic logic or user PDF bytes.

## Limits
These are focused source-level corrections. New PDFs have not yet been generated through the full ChronoSeal pipeline; the report-wide visual consistency and PDF signature validation are NOT VERIFIED. Release blocked.
