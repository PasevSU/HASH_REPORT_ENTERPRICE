# Precision audit — release blocked

Change: `Pipeline.generate` now requires exactly one freshly generated PDF with the expected `_HASHREPORT_TYP_SINGLE.pdf` or `_HASHREPORT_TYP_COMBO.pdf` suffix. It refuses unrelated PDFs and ambiguous matches instead of selecting the newest arbitrary PDF.

Regression suite under Xvfb: 61 tests, 58 PASS, 3 FAIL. Remaining failures:
- `test_pdf_skips_generator_requirement`: obsolete assumption that PDF input requires no hash generator; current pipeline always builds a hash report, including PDF mode. Requires revised contract test, not bypassing preflight.
- `test_transactional_publish_contract`: checks legacy `shutil.copy2(sealed,publish_path)` source string. Current staged copy + SHA-256 check + `os.replace` is safer. Requires behavioral test, not weaker publication.
- `test_volume_order_and_single_pdf_section`: checks for visible `st_dev` and `st_ino`; these remain in storage-identity evidence JSON but are intentionally hidden in the reader-facing PDF. Requires evidence preservation test.

Unverified: real TSA end-to-end, Windows native GUI, independent signed source PDF validation, source-PDF annotation fidelity, restart/concurrency/failure rollback, full release qualification. This is NOT FINAL.
