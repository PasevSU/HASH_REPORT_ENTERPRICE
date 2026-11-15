# ChronoSeal v5.4.0 RC qualification

- RFC 3161 bridge syntax: **PASS**.
- Main project test suite: **156 passed, 8 subtests passed**.
- Report-generator test suite: **124 passed, 36 subtests passed**.
- Synthetic native-Windows START -> qualified STOP -> DSS/Certs -> final reopen: **PASS**; final PDF reopened and exactly two timestamps were independently reverified.
- Separate PDF timestamp-verifier CLI: **PASS** for both DocTimeStamp signatures with explicitly supplied TSA trust material.

The synthetic report's layout heuristic returned **REVIEW** for some header/footer and appendix positions. This is an internal presentation check only: it neither validates nor invalidates the PDF signatures, does not change the signed bytes, and is not required for a recipient to verify the report's evidence.

Technical integration status: **SYNTHETIC_E2E_PASS**. The run used synthetic fixture files, not a user report. This records successful operation and independent verifiability of the configured technical flow; it is not a legal opinion, a claim about the truth of report contents, or a guarantee of how a court will assess a particular submission.

The active STOP profile is InfoNotary QTSA at `http://ts.infonotary.com/tsa`, requesting policy `1.3.6.1.4.1.22144.3.4.1`. Its root (`7D408CB43A5FA8D2A7094EE4637973A8355AD156CF08D6AEEBB0A2A875C45FAB`) and issuing service CA (`A4527BA3CDB627494FAC2F58069B37969A3219CF9154B324314A5C97701BDFBF`) are provisioned from the provider's public certificate register and fingerprint-matched to the Bulgarian TSL. The issuing CA is not treated as the TSA signer: final validation requires the TSL identity in the signer chain, a path to the explicit root, and authenticated revocation evidence.

Current EU LOTL and Bulgarian TSL snapshots are provisioned under `trust/LOTL/`. The LOTL signer pin `E0A620FBB6747362BB933AC44169D676A553444716CF5F31605F12A22B8396B1` is certificate 2 in the Annex to OJEU C/2026/1944 and was matched to the current LOTL signer. The offline verifier successfully checked the LOTL signature, Bulgarian TSL signature, signer delegation, and InfoNotary qualified service status. Refresh and revalidate snapshots and the applicable OJEU notice before deployment updates. OJEU e-Journal authenticity information: https://eur-lex.europa.eu/TodayOJ/authenticity-eOJ.html and https://eur-lex.europa.eu/TodayOJ/listing.html.

One user-authorized live RFC 3161 test was issued for a random nonce; no user document or report hash was submitted in that probe. The provider returned the configured policy OID, and OpenSSL verified the response against the original request. ChronoSeal also validated the token signer chain to the explicit InfoNotary root, the TSL service status at `genTime`, and fresh CRL evidence; OCSP was unavailable. The probe evidence is retained in `qualification_logs/infonotary_rfc3161_test_20261009T051229Z_21f18e`.

The full PDF flow has since passed on a synthetic report fixture. The run is retained in `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8/`; the final report is `synthetic_dualstamp_e2e_20261009T052107Z_dab2e8/sealed_output/RPT-20261009-072111554-B45A6321_HASHREPORT_TYP_COMBO.pdf`. Its SHA-256 is `667d23af9013c7d65f1e3a8fbdaa5c68b31fc28411293f392c24efc0fbc1eee5`. The RFC 3161 audit records both START and qualified STOP as verified, `qualified_timestamp_status: VALIDATION_PASS`, final reopen/reverification, and physical DSS certificate coverage. The independent qualified STOP report records the LOTL/TSL and service status as valid, signer chain `GOOD`, CRL `GOOD`, and OCSP `UNAVAILABLE`.

The separate PDF timestamp verifier also returned `PASS` for both signatures. Its retained audit is `qualification_logs/synthetic_dualstamp_e2e_20261009T052107Z_dab2e8/independent-library-verification.json`. It was run with the FreeTSA root, InfoNotary root, and the InfoNotary service identity certificate (whose fingerprint is checked against the signed BG Trusted List). A recipient may use any PDF signature validator and independently check the file hashes; acceptance does not depend on ChronoSeal's internal `PASS` or evidence logs.

The package's repeatable PDF-signature check is:

```powershell
node bridge\verify_pdf.mjs --input <report.pdf> --output <verification.json> --root trust\FreeTSA\certificate-2.pem --root trust\InfoNotary\qualified-root.pem --root trust\InfoNotary\qualified-timestamp-ca.pem
```

This checks the two PDF DocTimeStamp signatures, ByteRanges, CMS/ESS, timestamping EKU, validity at `genTime`, and paths against the supplied trust material. The independent qualified STOP/Trusted List/revocation result is recorded separately in `qualified-stop-validation.json`; for this test it reports LOTL/TSL valid, signer chain `GOOD`, CRL `GOOD`, and OCSP `UNAVAILABLE`. A recipient can use an independent PDF signature validator instead of this package command.

The configured InfoNotary endpoint is HTTP, which exposes the submitted message imprint in transit. This is a transport-privacy warning, separate from the integrity and verifiability of the signed PDF. The synthetic report's layout `REVIEW` is likewise an internal visual heuristic, not a cryptographic or recipient-verification failure. No user report was processed in this synthetic run; suitability and procedural requirements for a particular court filing remain case-specific.

B-Trust Mobile provides user-driven document-signing functions, not the RFC 3161 QTSA endpoint. For German proceedings, eIDAS Article 41(2) concerns the rebuttable presumption of indicated time and data integrity for a genuinely qualified timestamp; it does not establish authorship or content truth and does not replace a qualified electronic signature or secure filing channel where required by ZPO §§ 371a/130a. See https://www.gesetze-im-internet.de/zpo/__371a.html, https://www.gesetze-im-internet.de/zpo/__130a.html, and https://eur-lex.europa.eu/eli/reg/2014/910/2024-05-20/eng.
