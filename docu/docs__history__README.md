# ChronoSeal One-Button Python RFC3161 Add-on — Windows v4.1 Release Candidate

Purpose: wrap the existing hash-report generator without changing its visible report layout, then apply independent external RFC3161 PDF DocTimeStamp revisions and perform final reopen/reverification.

## Windows first run
1. Extract the ZIP to a normal writable folder.
2. Run `Install_Windows.bat`. It verifies Python and Node >=22.12, installs `pdf-rfc3161`, runs regression tests, checks the bridge and imports the real dependency.
3. Run `Start_ChronoSeal.bat`.
4. Settings: select the real Hash Report Generator package (not needed for an already-generated PDF), START/STOP TSA URLs, and the approved trust certificate/chain files for each TSA.
5. Run Preflight. A BLOCKED result is fail-closed and must be resolved; it is not a timestamp PASS.
6. Run the one-button pipeline.

## Pipeline
Preflight -> existing report generator (or PDF bypass) -> preserve pre-RFC3161 PDF -> external TSA START -> verification -> external distinct TSA STOP -> verification -> write final PDF -> reopen final PDF -> extract timestamps again -> reverify every timestamp added by this run -> manifest + logs.

No local/self-generated TSA is used in the production path. `enableLTV` embeds validation candidates supplied/collected by the underlying RFC3161 engine; it is not by itself a claim of long-term legal validity.

## Windows controls and logging
The GUI has Run, Settings, and Diagnostics & Logs tabs; tool autodetection; generator package selection; Node/OpenSSL selection; START/STOP TSA and trust-file selection; progress; cancellation that terminates an active child process; live logs; and direct opening of logs/evidence folders.

Each run creates a timestamped session log directory with `chronoseal.log`, `environment.json`, per-command JSON records containing stdout/stderr/return code, and `error.txt` on failure. Successful evidence cases copy the complete session log bundle into the case and include its location in `manifest.json`.

## Release status
Local qualification can prove source integrity, regression behavior, Windows dependency gates, syntax and fail-closed policy. It cannot prove a public TSA endpoint/trust chain without the real configured TSA and network access. Therefore this package must remain a Release Candidate until a real Windows E2E run succeeds with the intended external START/STOP TSA providers and approved trust material.


## Automatic startup bootstrap (v4.1)
`Start_ChronoSeal.bat` is now the only normal entry point. The GUI automatically detects Node/OpenSSL, enforces Node >=22.12, verifies that `pdf-rfc3161` imports, runs `npm install --no-audit --no-fund` only when repair is necessary, repeats the import check, saves detected tool paths, and writes `logs/startup_latest.json`. The Run button stays disabled until startup qualification passes. `Install_Windows.bat` is retained as a compatibility launcher and no longer needs to be run manually first.


## Certificate embedding invariant (5.0 qualification)

Every certificate configured for a TSA provider is converted to DER and supplied to `pdf-rfc3161` as caller-provided `revocationData.certificates` while `enableLTV` is enabled. After each timestamp operation ChronoSeal compares DER SHA-256 values against the returned LTV certificate inventory. A configured certificate missing from that inventory blocks the run. Candidate certificate/OCSP/CRL bytes are also exported to the evidence directory. This proves the orchestration contract; production FINAL additionally requires a real `pdf-rfc3161` run and independent inspection of the written PDF DSS.


## v5.1 trust bootstrap
- START/DFN endpoint is preconfigured as `http://zeitstempel.dfn.de`, corroborated by current RWTH IT Center documentation.
- Missing DFN trust material is bootstrapped on Windows from a live RFC3161 response, then validated through Windows `X509Chain` with online revocation checking and exported to local PEM files.
- STOP/DigiCert trust material is downloaded only from DigiCert's official current timestamp certificate URLs, parsed by OpenSSL, stored locally, and then subject to the PDF DSS embedding invariant.
- ONE BUTTON automatically attempts trust bootstrap only when trust material is missing. It remains fail-closed on any network, chain, revocation, parsing, or trust failure.
- Hash Report Generator remains mandatory for source/folder input. Existing PDF input bypasses the generator by design.

## v5.2 integrated generator and TSA presets
The complete supplied Hash Report Generator v2.34 package is embedded under `hash_report_generator/`; no external generator folder is required. The default active profile is FreeTSA for START and DigiCert for STOP. Settings also contains provider presets derived from the supplied references. Taxpool is treated as a directory/list source, not as a TSA itself. QTSA qualified service is intentionally not assigned a fabricated endpoint; its free standard server is a separate preset. Aloaha's raw RFC3161 in-house endpoint is tenant-host specific; its external proxy is JSON-wrapped and is not exposed as a raw `pdf-rfc3161` profile.


## Aloaha project-scoped integration (v5.3)

Only RFC3161/PKI-relevant capabilities are represented: native `/csc/v2/signatures/tsa`, JSON timestamp-proxy capability boundary, and `/csc/v2/ocsp`. The tenant in-house TSA is non-qualified and requires explicit pinned/approved trust; ChronoSeal will not auto-trust a self-signed responder obtained from the network. Unrelated communications, wallet, signup, contact and discovery APIs are excluded.


## v5.3.5 RC - redundant RFC3161 verification
The RFC3161 bridge no longer treats `extractTimestamps()` as a single point of failure. Mandatory proof combines the library request-bound embed gate, independent PDF DocTimeStamp/ByteRange structure, OpenSSL RFC3161 verification over the exact ByteRange bytes, and a second OpenSSL verification after the final PDF is closed and reopened. The library extractor remains a corroborating verifier and is recorded as WARN if it returns zero/throws while all mandatory proofs pass.

## v5.3.6 RC - OpenSSL ByteRange verifier correction

Corrects the independent OpenSSL RFC3161 proof path: the RFC3161 token is passed via `-in token.tsr` and the exact PDF ByteRange-selected bytes via `-data signed.bin`. This fixes the Windows/OpenSSL 4.x `ts: Use -help for summary` failure caused by passing the ByteRange data as the token input. The redundant library, PDF-structure, raw-ByteRange and final-reopen gates remain enabled.

## v5.3.7 RC — trust-chain recovery + Windows GUI editing
- TSA bootstrap classifies X.509 certificates by Basic Constraints and self-signed status, validates signer→intermediate→root with OpenSSL, and on Windows recovers incomplete official bundles through live TSA token + Windows X509Chain/AIA.
- OpenSSL RFC3161 `-untrusted` bundle includes intermediate and embedded signer material; trust roots remain separate.
- Previously present but unqualified trust files are no longer silently accepted; only `trust_chain_validated` material is reused.
- Windows GUI editing: Ctrl+C/V/X/A, Ctrl+Insert, Shift+Insert, Shift+Delete, right-click Cut/Copy/Paste/Select all for Entry/Text/Combobox.
- Run log and Diagnostics have Copy selected / Copy all controls.
- Pipeline BLOCKED dialog is now a selectable/copyable text window with Copy selected / Copy all.

## v5.3.8 dual-DocTimeStamp transactional sealing

For generated hash reports ChronoSeal now treats the generator PDF as an **UNSEALED working artifact**. The requested `RPT-..._HASHREPORT_TYP_SINGLE/COMBO.pdf` name is published only after the bridge has committed and independently reverified exactly two RFC 3161 PDF document timestamps in order: START then STOP. The two tokens must be distinct. The final reopened PDF must expose exactly two `/Type /DocTimeStamp` objects and two `/SubFilter /ETSI.RFC3161` entries, and `/DSS` with `/Certs` remains mandatory.

All certificate bytes supplied for the selected START and STOP TSA providers (trust root, intermediate and TSA signer/embed material) remain fail-closed against the LTV certificate inventory. The audit now records a per-stage certificate inventory with SHA-256 fingerprints and the number of unique certificate fingerprints represented by the successful START/STOP LTV material. A zero-certificate final inventory blocks publication.


## v5.3.9 report-end declaration and certificate verifiability

- Moves the bilingual affidavit/declaration block after the visible STOP timestamp section.
- Removes the handwritten Pasev signature line/date block.
- Adds a precise bilingual explanation of DSS/Certs certificate extraction and independent X.509/RFC3161 verification.
- Clarifies that handwritten signature is not required for technical/cryptographic verification, without claiming that this replaces any procedural form requirement for an affidavit.
- Final ChronoSeal publication remains gated by the dual DocTimeStamp + DSS/Certs + reopen verification invariants.


## v5.4.0 RC - physical DSS certificate audit
- Final reopen now parses the physical PDF `/DSS /Certs` array and extracts each embedded X.509 certificate stream.
- Every expected START/STOP certificate SHA-256 must physically exist in the final PDF or the run is BLOCKED.
- Audit records subject, issuer, serial, validity, CA role, SHA-256 fingerprint, EKU OIDs and PDF object reference.
- Embedded report-generation mode no longer labels the later ChronoSeal stamping stage as a network failure; it points to the authoritative embedded DocTimeStamp/DSS state and final audit.
- This does not claim QES or qualified eIDAS timestamp status.

### v5.4.1 integration candidate
GUI asks separately for explanation and original PDF inclusion. Pre-seal composer merges sections and stamps text SHA-256 footers before RFC3161. Requires requirements-integration.txt. This is not a qualified release. Existing PDF input still bypasses report generation and is a known blocker for source-PDF inclusion.
