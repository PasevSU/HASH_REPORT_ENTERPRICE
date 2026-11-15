# DEV v41 — JS rule migration
- Migrated style/, modules/, report_profiles/ definitions from JSON to `.js` (module.exports).
- Python loaders dynamically discover `*.js` and resolve them through a bounded Node VM runner.
- Node.js runtime required; failure is explicit, no silent JSON fallback.
- Other JSON formats (case evidence, manifests, audit records, dependency metadata) remain JSON: these are **data**, not layout rules.
- ReportLab remains responsible for actual flowable measurement and page breaks; this migration alone does not fix all whitespace or pagination defects.
- Release blocked until all profile visual/cryptographic end-to-end tests pass.
