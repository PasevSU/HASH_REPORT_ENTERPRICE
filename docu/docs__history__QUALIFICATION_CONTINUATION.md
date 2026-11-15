# Qualification continuation — 2026-10-08

Baseline: ChronoSeal_v5.5.4_PRECISION_CANDIDATE_UNQUALIFIED.zip.

Updated three legacy regression assertions to reflect actual contracts without disabling tests:
- PDF embedding still requires a hash report generator.
- Atomic publish uses staged copy, SHA-256 equality, os.replace, then removal of intermediate report.
- Reader-facing Volume excludes st_dev/st_ino; evidence identity remains in storage JSON.

Regression command: `xvfb-run -a python -m unittest discover -s tests -p 'test_*.py' -q`.
Result: 61 tests, OK.

Release remains BLOCKED: real live TSA START/STOP, independent signature validation on representative signed PDFs, Windows native GUI, failure/concurrency/restart tests, and clean ZIP qualification not fully covered. This is not FINAL.
