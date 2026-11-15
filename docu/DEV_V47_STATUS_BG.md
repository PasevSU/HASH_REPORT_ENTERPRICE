# DEV v47 — PDF page identity footer centralization

- `hash_report_generator/style/96_page_identity.js`: central configuration for page identity footer.
- `chronoseal/page_identity.py`: loads PAGE_IDENTITY from the recursive JS style loader.
- Smoke test: 2-page A4 PDF; footer brand and per-page hashes confirmed in extracted text.
- 66 PDF generator unit tests PASS. Missing optional modules: rfc3161_validation, evidence_database.

## Known unresolved

- The real six-page user PDF has page 3 and page 5 under-filled. The legal companion is independently rendered and assembled. This patch does NOT fix pagination.
- Not all local canvas coordinates and appendix positions are centralized.
- No end-to-end cryptographic TSA signing or Windows GUI qualification.
- Release BLOCKED.
