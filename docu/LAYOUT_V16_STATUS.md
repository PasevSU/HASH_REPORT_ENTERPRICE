# DEV v16 — central ReportLab table migration

- `_apply_table_style()` in the shared core now delegates to `pdf_object_rules.reportlab_table_style()`.
- Paragraph headers are normalized centrally to white bold text.
- Seven table variants use the same palette, padding, grid and typography.
- Existing document content and crypto engines were not modified.
- Not yet migrated: independent direct TableStyle calls and PDF canvas rendering.
- Release blocked pending complete visual and cryptographic qualification.
