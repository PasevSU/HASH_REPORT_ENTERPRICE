# ChronoSeal migration qualification gates — DEV v22

Status: **RELEASE BLOCKED**. This package is a migration baseline, not a completed migration.

## Fixed scope

- Four primary reports: SINGLE, SINGLE_PDF, COMBO (nonrecursive), COMBO_ALL (recursive).
- Shared RFC3161 START → Process Modules → RFC3161 STOP; final PDF stamping, DSS and independent verification occur according to signature-preserving PDF lifecycle.
- Process modules are executable operations, not merely content headings.
- Style/ exclusively owns visual definitions; profiles select module sequence; automation/ owns BAT launchers.
- OTS / Blockchain Verification excluded from this phase.
- Existing VOLUME and legacy functions preserved pending full inventory; never delete to pass a gate.

## Current verified work

- Added combo_all.json profile with recursive_folder scope.
- Added profile-reference, enumeration and scope contract tests.
- Generated baseline inventory with file hashes and explicit partial/unverified status.

## Release blockers

1. SINGLE_PDF profile does not execute PDF combination.
2. Real RFC3161 START/STOP and dual-provider failover are not proven in modular flow.
3. Direct ReportLab styles remain in modular_report.py and other generators.
4. No independent CMS, ByteRange, DSS, CRL/OCSP and PAdES regression verification.
5. Automation BAT launchers not unified for four profiles.
6. No end-to-end real input → signed PDF → independent verification qualification.
7. No full regression inventory comparing donor ZIP versions and GUI.

No new version may be marked RELEASE until all mandatory entries PASS and the freshly extracted ZIP passes the same gates.
