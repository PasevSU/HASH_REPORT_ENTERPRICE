# ChronoSeal Modern Layout DEV v8

## Implemented
- Shared COMBO table column proportions (100% of configured 170 mm width).
- Wider row number and filename columns; no digit splitting for index cells.
- Full 64-character SHA-256 digest preserved, displayed in 16-character chunks.
- KB units omitted from cells because the table header declares KB.
- Both main COMBO generator and bridge helper use shared cell formatting.

## Not yet verified
- Full PDF end-to-end generation with actual TSA providers.
- Pixel-level visual comparison with supplied reports.
- Unicode path font coverage and unwanted page breaks.
- SINGLE+PDF and COMBO_ALL full cryptographic validation.

Release qualification: BLOCKED. Do not stamp or edit already signed example PDFs.
