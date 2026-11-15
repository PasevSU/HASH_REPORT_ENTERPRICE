# DEV v26 visual qualification

This suite uses synthetic inputs and produces **unsigned** PDFs for all four report profiles. It checks successful rendering, page count and text presence. This is not pixel-based comparison with the user reference PDFs, not cryptographic verification and not an Enterprise release gate PASS.

Run: `python qualification/visual_qualification.py --output qualification/output`

Original working signing bridge and legacy renderers remain unchanged. The isolated modular renderer now uses LongTable with repeated headings and section keep-with-next.
