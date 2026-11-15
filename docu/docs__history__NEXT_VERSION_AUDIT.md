# Next-version candidate — NOT QUALIFIED

Changes: short Volume display (full raw storage identity remains in evidence JSON), optional output folder checkbox (default is input working folder), recursive COMBO `_ALL` naming, and manifest output_directory.

Verification: `xvfb-run -a python -m unittest discover -s tests -q`: 61 tests, 3 failures. Failures: test_pdf_skips_generator_requirement; test_transactional_publish_contract; test_volume_order_and_single_pdf_section (legacy expectation for visible device ID). Two new focused output-policy tests passed. Syntax compilation passed.

Not verified: end-to-end START/STOP with real TSA, Windows UI, independent verification of signed source PDFs, regression release gate. DO NOT LABEL FINAL.

Known limitation: generator discovery still scans candidate directories and needs a deterministic output contract; recursion scanning and generated artifacts require additional regression testing. Existing files and cryptographic mechanisms were not intentionally changed.
