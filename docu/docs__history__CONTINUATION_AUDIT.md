# Continuation audit — not qualified

Corrected GUI start(): removed function-local tkinter.messagebox import that shadowed the module-level import and caused UnboundLocalError before startup qualification.

Test run: xvfb-run -a python -m pytest -q => 74 passed, 2 failed.

Remaining failures:
- tests/test_pipeline.py::Tests::test_pdf_skips_generator_requirement: legacy test assumes PDF input does not require a generator; current SINGLE_PDF design does require the hash report generator. Needs contract reconciliation, not weakening the preflight.
- tests/test_v538_dualstamp_transaction.py::V538Contract::test_transactional_publish_contract: asserts literal `shutil.copy2(sealed,publish_path)` while implementation copies to .publishing, checks SHA256, then atomically replaces final. Needs behavior-level regression test; do not regress atomic publishing.

Real signed/timestamped PDFs and live RFC3161 providers not end-to-end tested. Windows GUI not tested. Release BLOCKED.
