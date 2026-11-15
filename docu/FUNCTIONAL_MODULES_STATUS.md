# DEV v21 — Functional modules

The `hash_table` module performs real file discovery and streaming hashing in `single_file`, `current_folder`, and `recursive_folder` scopes. `report_profiles/*.json` select scope and module order. Hash table renderer supports single-file Property/Value and multi-file tables with repeated header rows. It excludes the output PDF and detects changes during hashing. No fabricated hashes or metadata.

**Limitations:** Existing legacy PDF generators remain separate; RFC3161/OTS/PKI flows not migrated; renderer uses direct TableStyle values and therefore full visual migration remains pending. `ctime` on Unix is metadata-change time rather than file creation time; this field requires platform-aware treatment before evidentiary release. DEV / RELEASE BLOCKED.

The legacy report package now includes its `rfc3161_validation` and
`evidence_database` modules. Standalone RFC 3161 report generation verifies
the CMS signer, critical time-stamping EKU, certificate validity at `genTime`,
the chain against explicitly configured, ChronoSeal-pinned, or bundled CA trust roots, and signed CRL
and OCSP evidence when available. Network or missing revocation evidence is
reported as `UNAVAILABLE`, never as `GOOD`; a revoked signer and a failed
certificate chain are rejected. The SQLite evidence database stores report
metadata, file hashes, timestamp responses, and binary certificate/revocation
artifacts. ChronoSeal's bridge continues to perform the production PDF
START/STOP sealing and independent final verification; these modules do not
make the unsigned modular renderer a signed or timestamped report generator.

Synthetic regression tests exercise valid, stale, invalid-signature, and
revoked CRLs; OCSP tests cover `CertID` mismatch, response freshness, delegated
responder authorization, and `GOOD`/`REVOKED` outcomes. Their network responses
are locally generated or mocked: they are not a live TSA/OCSP/CRL qualification.

`SINGLE_PDF` can embed a source PDF containing signature fields or PDF
DocTimeStamp dictionaries. The original is retained as a byte-exact attachment,
and the report records the detected signature objects and attachment SHA-256.
Visible source pages are derived presentation copies with a footer strip; the
source signature authenticates only the byte-exact attached original, not those
copies or the combined report. The signature inventory is not cryptographic
signature validation. The default STOP policy uses an InfoNotary QTSA profile
and binds the requested and returned RFC 3161 policy OID. The OJEU
C/2026/1944 LOTL signer certificate, current EU LOTL and Bulgarian TSL
snapshots, and InfoNotary root and service CA are provisioned; the list
signatures, delegation, service identity, and published fingerprints have
been checked. The endpoint is `http://ts.infonotary.com/tsa`; HTTP exposes
the submitted message imprint. Before final PDF publication, the bridge
checks service status and signer identity at the token's exact `genTime`,
validates the signer chain to the explicit InfoNotary root, and requires
authenticated CRL or OCSP evidence. Missing, unknown, stale, or revoked
evidence blocks publication. A user-authorized nonce-only InfoNotary RFC 3161
test returned the configured policy and passed request-bound OpenSSL
verification, chain-to-root, TSL service-status and fresh CRL checks (OCSP
was unavailable). A separate authorized synthetic end-to-end test has now
passed report generation, START + qualified STOP stamping, signer/service/
revocation validation, DSS certificate coverage, final reopen and independent
verification of exactly two timestamps. Its evidence and final PDF are
retained under `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8`.
The report-layout audit returned `REVIEW` for header/footer and appendix
positions; this is an internal presentation heuristic, not a condition for
independent PDF signature or hash verification. The external TSA tokens and
embedded verification material are the recipient-checkable evidence; a
ChronoSeal validation result is not required for that check. No user report
was timestamped in this synthetic run, and the HTTP endpoint exposes the
submitted message imprint in transit.

Each successfully sealed ChronoSeal report is also archived before its final
output is published. The GUI's Settings tab controls the archive root and
SQLite database path; `config/config.json` is the single settings source.
Numbered report folders contain the final PDF, root manifest, run log, and
evidence directory. SQLite indexes each bundle in `archive_reports` and stores
the exact bytes, length, and SHA-256 for every file in `archive_files`.
Duplicate report IDs are never overwritten, and an archive/database failure
blocks final PDF publication. Archive/database settings are validated during
preflight, before the timestamping pipeline begins.
