# v64 central table migration: qualified status

The single reference design is `FILE INFORMATION` with white bold centered headings on a dark header, alternating light rows, asymmetric edges and offset shadow. Shared colors, typography selectors, padding and edge rules are loaded from `hash_report_generator/style/30_tables.js` via `reportlab_table_style()`.

**Incomplete migration:** local TableStyle constructors remain in bridge layout panels, legacy table builders and modular renderer. A clean migration requires classifying decorative layout tables separately, eliminating remaining style overrides, and running signed production flows. No full release claim is made.
