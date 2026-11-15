# DEV v17 — central ReportLab migration

- SINGLE and COMBO now consume the same title flowables and QR/legal table styles from `pdf_object_rules.py`.
- H2 (14 pt bold), H1 (20 pt bold), H3 (11 pt regular) are applied to real generator paths.
- Legal copy, QR payload, evidence data, and cryptographic functions are unchanged.
- Remaining local visual rules (canvas/footer, miscellaneous tables) require migration and real full-report validation.
- RELEASE BLOCKED pending comprehensive qualification.
