# Layout qualification — real SINGLE PDF

Input: RPT-20261008-162513251-8D3C2498_HASHREPORT_TYP_SINGLE.pdf (6 pages).

The read-only preflight flags large unused body regions on pages 3 and 5; the STOP timestamp section flows onto page 3; the ZUSAMMENFASSUNG table leaves an orphan row on page 5. Layout status: FAIL.

Other visually confirmed issues requiring fixes: page 1 uneven scaling of legal notice/QR and dense hash table; footer page-hash text too small; page 6 checksum appendix has excessive separation between main table and explanatory notes.

Next engineering actions: centralize reserved footer and frame geometry; implement section-level keep-with-next and table tail minimum rows in the actual generator; remove forced breaks only after ensuring no signature or evidence is altered; rerender all four profiles and check page-by-page. This v35 audit tool detects issues; it does NOT fix report layout and does NOT restamp signed PDFs.

Run: python tools/pdf_layout_audit.py report.pdf --output report.layout.json
