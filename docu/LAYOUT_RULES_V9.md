# Binding PDF rules — v9

This changes ReportLab rendering rules in the actual generators, not only CSS.

- A4 210×297 mm; physical margins 20 mm left/right, 25 mm top, 20 mm bottom.
- ReportLab SimpleDocTemplate has 6 pt internal frame padding on each side: effective available width is ~165.77 mm. Tables are capped at 165.5 mm, avoiding overflow and unexpected horizontal placement.
- Seven COMBO column ratios: 6.5 / 26.5 / 10 / 8.5 / 14.5 / 14.5 / 19.5 percent.
- Cell padding 2.5 pt; index uses no-break markup; table repeatRows=1 and splitByRow=1.
- Table header text explicitly white on dark background (Paragraph text colors override TableStyle TEXTCOLOR).
- Full 64-character SHA-256 retained and displayed in fixed groups; do not use digest truncation.
- These are *layout* changes only, not proof of RFC3161 validation or full release qualification.
