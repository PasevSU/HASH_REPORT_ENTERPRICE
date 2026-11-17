# ChronoSeal - HASH_REPORT_ENTERPRICE

ChronoSeal turns a folder into verifiable evidence. It hashes every file the
operator selected, builds one combined PDF report, seals it with an RFC 3161
time-stamp and archives the case in a local SQLite database, so the state of that
folder can still be proven later, on another machine, without the original data.

> **This is the CLI edition (`release/cli`).** There is no graphical interface in
> this branch: one word names the report, one argument names the file or folder.
> The GUI edition, without any verification QR and meant for quick actions and
> sending by e-mail, lives on `release/gui`; both branches derive from `main`.
>
> It is a **package for adaptation**. Every report closes with a verification QR
> link, and the address it is published under has to redirect that one link to
> **two** documents - the report and its proof bundle. This code creates neither
> the redirect nor a `.ots` file, so the last step belongs to your server: see
> [The verification URL is yours to redirect](#the-verification-url-is-yours-to-redirect).

|  |  |
|---|---|
| Version | 5.10.0-cli |
| Platform | Windows 10 / 11 (x64) |
| Runtime | Python 3.12+ and Node.js 22.12+ |
| Interface | Command line only: report names over `chronoseal_cli.py` |
| Licence | Proprietary, all rights reserved - see [LICENSE](LICENSE) |

## What a run produces

* one PDF report per selected scope (single file or combined folder report),
* SHA-256 / SHA-512 digests for every included file, plus size and timestamps,
* an RFC 3161 time-stamp taken from qualified providers (`DUAL-STAMP` mode by
  default, with LTV material and an EU trusted-list check),
* an evidence manifest (JSON) describing exactly what was hashed, what was
  excluded and why,
* a numbered entry in the local archive database, so report numbers are never
  reused.

The report is only published when every file in the selected folder could be
read. A hash report that silently omits evidence is worse than no report, so a
partial run ends as `BLOCKED` with the offending paths and the remedy.

## Embedding a PDF in the report

The report can carry an original PDF inside it - visible pages for a human
reader and a byte-exact copy as an attachment. Which file is embedded depends on
the report type, and the choice is visible in the published name:

| Report type | Embedded file | Published as |
|---|---|---|
| `SINGLE_PDF` | the single input file | `..._HASHREPORT_TYP_SINGLE_PDF.pdf` |
| `COMBO_PDF` | one PDF chosen by the operator | `..._HASHREPORT_TYP_COMBO_PDF.pdf` |
| `COMBO_ALL_PDF` | one PDF chosen, folder scanned recursively | `..._HASHREPORT_TYP_COMBO_ALL_PDF.pdf` |

`_ALL` always sits before `_PDF`, because the generator emits `..._SINGLE` /
`..._COMBO` and the suffixes are added at publication. A name such as
`..._COMBO_PDF_ALL.pdf` never exists, and the JavaScript clone uses the same rule.

`--embed-position before|after` (default `after`) places the embedded pages in
front of the hash report or behind it. The run records the decision in
`embedded-original.json` (`embed_position`, `first_visible_page`, `visible_pages`)
and prints `First source page in file` in the report itself, so a reader can find
the attachment without guessing.

```powershell
python chronoseal_cli.py C:\cases\2026-08 \
  --embed-pdf C:\cases\2026-08\Ergaenzungspflegschaft.pdf \
  --embed-position before --recursive
```

The orchestrator exposes the same three controls without a dialog: the report
name decides whether anything is embedded (`SINGLE_PDF`, `COMBO_PDF`,
`COMBO_ALL_PDF`), `--pdf` names the file and `--position` names the side. The
naming rules live in `chronoseal/embed_options.py`, so the name an operator types
and the type the pipeline publishes cannot drift apart.

Embedding fails closed, with a code per type:

| Code | Meaning |
|---|---|
| `EMBED_POSITION_INVALID` | position is neither `before` nor `after` |
| `EMBED_PDF_SOURCE_MISSING` | the chosen PDF does not exist |
| `EMBED_PDF_SOURCE_INVALID` | the chosen path is not a readable PDF |
| `{SINGLE_PDF,COMBO_PDF}_SOURCE_ENCRYPTED` | an encrypted source is never opened silently |
| `{SINGLE_PDF,COMBO_PDF}_SOURCE_SIGNATURE_AUDIT_FAILED` | the source signature could not be audited |

Only one PDF can be embedded per report: the attachment is the one original, and
two originals would make the report ambiguous. The embedded file is never
re-compressed or re-sampled, and it can never be the evidence target itself.

Two wrappers drive the sealed path for the new types:
`automation\COMBO_PDF.bat` and `automation\COMBO_ALL_PDF.bat`, both taking
`INPUT_PATH OUTPUT_DIR EMBED_PDF [before|after]`.

## Verification QR at the end of the report

A sealed report is verifiable only if the reader can reach the evidence, so the
closing block is mandatory: every generated PDF ends with a QR code plus a
bilingual (DE/EN) statement that the code leads to the electronic documents for
the timestamps in this report: the RFC 3161 responses for START and STOP, the TSA
certificates with their trust chains, CRL/OCSP status and the OpenTimestamps
proof. The text says explicitly that the report documents one file or several
files, that the link delivers the report and its verification files together
(a single file or a ZIP archive, depending on what was archived), and what the
`.ots` companion is - a separate small file anchoring the SHA-256 of this very
PDF in the Bitcoin blockchain, created only after the report is sealed, starting
as a pending calendar confirmation and checked with `ots verify`. ChronoSeal does
not create that proof; the block explains the file the verifier receives from the
same link. The block is a pointer only: no hash, signature or timestamp is
changed by it, and the embedded original PDF pages stay byte-exact.

The address cannot be filled in advance, because the code names the upload slot of
one report. The pipeline therefore builds it once per run - the configured base
address plus a random 37-digit code in `10-4-4-4-15` groups - hands it to the
generator and records the same address in the evidence case:

```
CHRONOSEAL_EVIDENCE_BASE_URL -> config['verification']['base_url']
                             -> https://pasev.asuscomm.com/static/
```

```powershell
python chronoseal_cli.py C:\cases\2026-08
```

There is no checkbox and no URL field: `--url` (see
[below](#the-verification-url-is-yours-to-redirect)) sets the host for the run, and
the run prints the resulting base address and a one-line read-back before anything
is generated. `--qr-url` still exists, but it *overrides* the generated link
instead of enabling it, for installations that already know where the files will be
published (`qrcode` is used when installed; if it is missing the block still prints
the address with a note that the image could not be drawn).

The run fails closed twice. `VERIFICATION_QR_INVALID` refuses an unusable base
address before anything is generated. `VERIFICATION_QR_NOT_APPLIED` rejects a
report whose evidence case has no `verification-qr.json`, or one that names a
different URL, so a report can never look cross-referenced when it is not. The
manifest records `verification_qr`, `verification_qr_code`, `verification_qr_url`,
`verification_qr_position`, `verification_qr_record` and
`verification_qr_rendered`.

## The verification URL is yours to redirect

The base address is an input to this package, not a promise it can keep alone:

```powershell
python chronoseal_report.py COMBO_ALL D:\cases\2026-08 --url https://example.net/static/
```

`--url` wins over `CHRONOSEAL_EVIDENCE_BASE_URL` and over
`config['verification']['base_url']`, and a trailing slash is added when it is
missing. The run appends one generated code per report, so the address written into
that report is unique to it:

```
https://example.net/static/1a2b3c4d5e-1234-5678-9abc-def012345678901
```

For that link to be worth printing, the host behind it must redirect it to **two**
documents: the sealed report this run published, and the proof bundle that belongs
to it - RFC 3161 responses, TSA certificates with their chains, CRL/OCSP status and
the OTS proof, either as one archive or as the two files. Everything needed to build
that mapping is recorded in the evidence case next to the report:
`verification-qr.json` holds the code and the exact address, the manifest repeats it
in `verification_qr_code` and `verification_qr_url`, and `report.pdf` / `rfc3161/`
plus the OTS file are the payload the redirect has to reach.

Two consequences, stated plainly:

* this code creates **no `.ots`** file and uploads nothing - the OpenTimestamps
  proof anchors the SHA-256 of a report that does not exist yet, so it has to be
  made after the seal, outside this package;
* a QR that points at an address where nothing redirects is a dead link, so the
  redirect is part of the deployment, not an optional extra.

## Requirements

| Component | Minimum | Used for |
|---|---|---|
| Python | 3.12 | pipeline, report generation |
| Node.js | 22.12 | PDF rule engine and the RFC 3161 bridge |
| OpenSSL | 1.1.1 / 3.x | independent time-stamp verification |

`Install_Windows.bat` checks all three, installs `requirements-integration.txt`,
locks and verifies the Node dependency, runs the dependency self-check and then
launches the application.

## Install and launch

```
Install_Windows.bat      # first run on a new machine: verify, install, prepare
Run_Report.bat           # report-name orchestrator (wraps chronoseal_report.py)
Run_Diagnostics.bat      # full diagnostic sweep, safe to run any time
js\HashReport.bat        # menu launcher for the pure JavaScript clone
```

`Install_Windows.bat` is the only step that installs anything: it verifies Python,
Node.js and OpenSSL, installs `requirements-integration.txt`, locks and verifies the
Node dependency, runs `chronoseal.selfheal` and prints the report names. It launches
nothing, because there is no window to open: after a successful install the next
command is a report. `Run_Diagnostics.bat` reports the state of every required
component at any time. No browser, WebView or HTTP channel is used anywhere.
`js\HashReport.bat` is the launcher of the pure JavaScript clone: it collects the folder, recursion, filter patterns, per-file mode, archive, layout gate, report type, the embedded source PDF, the PDF to include and where that PDF goes (`before` / `after`) in a menu and then calls `node js/cli.mjs`, so it needs Node.js only. See `docu/JS_CLONE_BG.md`.

## Report names

One word names the report; the input decides the mode and the name decides the
assembly. `chronoseal_report.py list` prints the same table as a reminder.

| Report | Input | What it publishes |
|---|---|---|
| `SINGLE` | one file | sealed report for that file |
| `SINGLE_PDF` | one PDF | sealed report with the input embedded byte-exact |
| `COMBO` | one folder or an explicit file set | sealed report for that evidence set |
| `COMBO_PDF` | one folder plus `--pdf` | the same, with that PDF embedded before or after the report |
| `COMBO_ALL` | one folder | sealed report for the folder and every subfolder |
| `COMBO_ALL_PDF` | one folder plus `--pdf` | the recursive report with that PDF embedded |

```powershell
python chronoseal_report.py SINGLE  C:\cases\letter.pdf
python chronoseal_report.py COMBO   C:\cases\2026-08 --output-dir D:\evidence
python chronoseal_report.py COMBO_ALL_PDF C:\cases\2026-08 `
  --pdf C:\cases\Anlage.pdf --position before --url https://example.net/static/
```

A report name that does not match the input is refused before anything is hashed:
`COMBO` on a file, `SINGLE` on a folder, `_PDF` without `--pdf`, `--pdf` on a report
that embeds nothing. The orchestrator only validates and translates; the run itself
is the same `chronoseal_cli.py` path, so logs, exit codes and evidence are identical.

## Choosing the evidence

* **A folder** is scanned as it is, or with `--recursive` (`COMBO_ALL`).
* **File-type filters** chain: `--filter '*.eml' --filter '*.pdf'` keeps files that
  match any of them, and the next filter field is simply another `--filter`. A chain
  that matches nothing stops the run with exit code `3`
  (`FILTER_MATCHED_NO_FILES`): nothing is hashed, no report number is consumed and
  no report is published.
* **An explicit file set** names the evidence one path at a time:
  `--file a.pdf --file sub\b.pdf`. The target folder becomes optional - the deepest
  folder that contains every chosen file is used as the evidence root - and the
  selection cannot be combined with `--filter` or with a recursive report.

A file that cannot be read blocks the run before publication, exactly as in the
folder-scoped path: a combo report is never published with missing evidence. The
applied chain and the chosen files are stored in the report and in the evidence
manifest (`selection_filters`, `selection_files`, `selection_paths`,
`selection_root`), so a reader can see how the evidence set was built. Filtering
lives in `hash_report_generator/file_filters.py` and the selection in
`hash_report_generator/file_selection.py`, both tested without any interface.

## Command line

`chronoseal_report.py` is the front door (see [Report names](#report-names));
`chronoseal_cli.py` is the same run without the naming layer:

```
python chronoseal_report.py list              # report names and the URL contract
python chronoseal_report.py --information     # what this edition expects
python chronoseal_cli.py <file-or-dir> --recursive --log-dir logs
python chronoseal_cli.py --preflight          # checks only, no sealing
python chronoseal_cli.py --bootstrap-trust    # refresh TSA trust material only
python chronoseal_cli.py <target> --json      # one JSON line on stdout, logs on stderr
python chronoseal_cli.py --self-check         # verify and repair dependencies
```

Exit codes: `0` PASS, `2` BLOCKED (see `error.txt` in the session log), `3` a
filter chain matched no file, `130` cancelled with `Ctrl+C`. Session logs,
`environment.json` and every executed command are written to `--log-dir`.

The JavaScript clone carries its own CLI (`node js/cli.mjs --help`) and a
programmatic API; how to obtain and drive them from another machine is described in
[Consuming the repository from GitHub](#consuming-the-repository-from-github).

## Configuration

`config/config.json` is the single source of truth. The keys that change
behaviour most often:

| Key | Default | Effect |
|---|---|---|
| `generator.allow_unreadable_files` | `false` | `true` publishes the report and records every exclusion in `discovery-unreadable.json` |
| `generator.follow_links` | `false` | do not descend into junctions and symlinked directories |
| `generator.idle_timeout_seconds` | `900` | kill a child that produces no output for this long |
| `generator.timeout_seconds` | `0` | absolute cap, `0` means no cap |
| `generator.heartbeat_seconds` | `30` | "still running" line interval |
| `rfc3161.mode` | `DUAL-STAMP` | one or two independent time-stamp providers |
| `rfc3161.hash_algorithm` | `SHA-512` | digest used for the time-stamp request |
| `repair.enabled` | `true` | verify and restore the pinned Node dependency |
| `repair.allow_network` | `false` | an evidence tool never reaches PyPI or npm silently |

## Self-healing dependencies

Before every run the pipeline verifies the Node package `pdf-rfc3161` against the
hash-pinned manifest and, if it is missing or damaged, restores it byte for byte
from `vendor/pdf-rfc3161` (no network needed). It then proves with a real
`import()` that the package loads, retrying once so a transient Windows
file-lock cannot block a run. Every action is logged as `SELF-HEAL: ...`.

```
python -m chronoseal.selfheal                            # verify + repair
python chronoseal_cli.py --self-check --repair-network   # allow network repair
```

`Install_Windows.bat` and `Run_Diagnostics.bat` run the same check, so a freshly
installed machine and a run-time machine end up in the same verified state.

## Evidence discovery policy

A combined report covers exactly the folder the operator selected, and it either
hashes every file there or refuses to publish. Discovery is bounded and
deterministic: it never walks `node_modules`, virtualenvs, `vendor` or caches,
and it never matches a file by arbitrary recursion order. Read failures are
reported with the concrete cause (`cloud placeholder`, `access denied`,
`file is in use`, ...) instead of a bare `[Errno 22] Invalid argument`, and a
briefly locked live file is retried twice before the run fails.

The generator is bounded by progress rather than by total runtime: a very large
input may finish while a hung child is still killed.

## Audit hardening

`tests/test_hardening.py` locks in the defects found by the expert audit so none
of them returns silently. The list includes child-process hygiene (explicit
`stdin=subprocess.DEVNULL`, `CREATE_NO_WINDOW`), one probe per external tool, one
repair policy shared by every entry point and the pipeline, archive atomicity (a published
report folder is removed when the SQLite transaction does not commit), style
loading that survives a denied `realpath`, a watchdog termination fallback, and
a release gate that really runs every test module.

## Performance

Version 5.5.1 moved two hot paths off the per-file loop without touching a single
produced byte:

| Path | Before | After | Gain |
|---|---|---|---|
| JS rule loading, 32 rule files | 31.87 s | 13.67 s | 2.33x |
| `load_styles()` first call | 20.09 s | 7.41 s | 2.71x |
| `load_styles()` repeat call | 20.09 s | 0.002 s | process cache |

The merged style payload is byte-identical to the previous implementation
(SHA-256 `8fc6eceba632695a8b7892306bc65e9a604686c92c0a2047ef8a4dcdda28ae66`),
which the test suite pins together with its twelve rejection paths.

## Tests

```
npm test        # unittest discovery over tests/ and hash_report_generator/tests
npm run verify  # release gate: syntax, vendor integrity, self-check, doctor, tests
```

Current state on a real SMB tree:

```
pytest tests -q                     the whole Python edition
python -m unittest discover -s hash_report_generator/tests
node --test tools/pdfnorm/test/ tools/jsx/test/
node --test js/test/
```

The JavaScript clone has its own suite, `node --test js/test/` (50 tests: 7 core,
8 workflow, 8 API, 17 embedded PDF, 10 report type), which needs no Python and no
network, and covers the eight report types, the three-pass page-text hashing, the
embedded-PDF position and the published marker of every type.

Run the suites with `python -m unittest` / `python -m pytest` from the checkout.
Do not use `npm test` or `npm run verify` from a UNC path: Windows starts
`cmd.exe` in `C:\Windows` for those scripts, `-s tests` then resolves through
`sys.path` to the unrelated `tests` package shipped inside `site-packages`
(bitcoinlib), and the gate silently measures a foreign suite - 661 "tests" with
failures that have nothing to do with this project. The same fallback breaks
`npm run doctor` and `npm run verify:vendor`. Run the gate from a local drive, or
call the two `python -m unittest` commands directly.

`tests/test_report_orchestrator.py` covers the report names, the name/input
match, `--file`/`--filter` and `--url` with its precedence over the configuration
and the environment. The acceptance suites that drove Tk widgets live on
`release/gui`; this branch has no widgets to drive.

## Brand identity

The interface carries the **ChronoSeal(TM) Enterprise** identity introduced in v5.5.1: navy
`#0B1F3B` primary, blue `#1E64D6` accent, gold `#D4AF37`, `#E6EEF7` background
and white surfaces, with Inter for the interface and Source Sans 3 for documents
(both fall back to Segoe UI / the system mono face when they are not installed).

Every colour, font stack, icon and product string lives in one module,
`chronoseal/branding.py`. The CLI edition keeps the palette for the surfaces it
still renders (console headings, the report footer lockup) and the product strings
that name the release; the graphical surfaces that read the same module live on
`release/gui`.

The **PDF report palette is deliberately untouched**. The report is a forensic
document: its style bundle feeds the golden payload hash, so rebranding it would
invalidate the verification path for reports already issued. Branding stops at
the command line - see [docu/BRANDING_V551_BG.md](docu/BRANDING_V551_BG.md).

## Repository layout

```
Run_Report.bat                launcher for the report-name orchestrator
chronoseal_report.py          report-name orchestrator (SINGLE, COMBO, *_PDF, *_ALL)
chronoseal_cli.py             headless runner: flags, logs, exit codes
chronoseal/                   pipeline, settings, self-heal, QR rules, i18n,
                              branding (palette, fonts, icons, product strings)
hash_report_generator/        generator, JS rule loader, file filters, selection, tests
automation/                   sealed wrappers for the diagnostic runtime (no window)
tests/                        integration and hardening suites
js/                           pure JavaScript clone: CLI, programmatic API, PDF
                              layer, six per-type report modules, its own tests
trust/                        public CA / TSA material and the EU trusted list
docu/                         design, upgrade plan and test evidence (Bulgarian)
config/config.json            runtime configuration
```

## Documentation

| File | Content |
|---|---|
| `docu/V89_CURRENT_STATE_BG.md` | behaviour of the program before the upgrade |
| `docu/V89_UPGRADE_PLAN_BG.md` | every planned addition, test and its status |
| `docu/V89_UI_TEST_REPORT_BG.md` | iteration log, full-suite evidence, known limits |
| `docu/V90_JS_CAPABILITY_ANALYSIS_BG.md` | what can move to JS, with measurements |
| `docu/V92_CURRENT_STATE_BG.md` | how the CLI edition works today |
| `docu/V94_VERIFICATION_QR_BG.md` | the mandatory closing QR block and its address |
| `docu/V95_CLI_EDITION_BG.md` | CLI edition: report names, `--url`, the redirect contract |
| `docu/BRANDING_V551_BG.md` | brand identity: palette, fonts, icons |
| `docu/JS_CLONE_BG.md` | JavaScript clone: stages, CLI, API, six report types, three-pass hashing, tests |
| `docu/PDFNORM_JS_BG.md` | the `tools/pdfnorm` PDF/A-2b normaliser used by the clone |

These documents are written in Bulgarian because they are the working record of
the project; the code, the comments and this README are in English.

## Consuming the repository from GitHub

Short answer: **GitHub can serve these files, it cannot run them.** The repository is
public, so every committed file is reachable over HTTPS, but there is no hosted
endpoint, no upload API and no server-side generation - a report is always produced
by the clone in your own process, on your own machine. GitHub is the distribution
channel, not the service.

> **Check the URL before you build on it.** A path added in a newer commit is `404`
> on an older tag, so confirm the exact file answers `200` at the ref you pinned:
>
> ```powershell
> curl.exe -s -o NUL -w "%{http_code}`n" https://raw.githubusercontent.com/PasevSU/HASH_REPORT_ENTERPRICE/main/js/api.mjs
> ```

### What is addressable

| Need | Endpoint |
|---|---|
| One file, no authentication | `https://raw.githubusercontent.com/PasevSU/HASH_REPORT_ENTERPRICE/main/<path>` |
| One file, with metadata (size, sha) | `https://api.github.com/repos/PasevSU/HASH_REPORT_ENTERPRICE/contents/<path>` |
| Whole tree, one request | `https://api.github.com/repos/PasevSU/HASH_REPORT_ENTERPRICE/git/trees/main?recursive=1` |
| A pinned snapshot | `https://github.com/PasevSU/HASH_REPORT_ENTERPRICE/archive/refs/tags/<tag>.zip` (or `.tar.gz`) |
| A release asset | `https://github.com/PasevSU/HASH_REPORT_ENTERPRICE/releases/download/<tag>/<asset>` |
| Metadata only (tags, assets) | `https://api.github.com/repos/PasevSU/HASH_REPORT_ENTERPRICE/releases` |

Three copy-paste examples:

```powershell
# raw file
curl.exe -sO https://raw.githubusercontent.com/PasevSU/HASH_REPORT_ENTERPRICE/main/js/api.mjs

# contents API: base64 payload, use it when you also want the blob sha
$r = Invoke-RestMethod https://api.github.com/repos/PasevSU/HASH_REPORT_ENTERPRICE/contents/config/config.json
[IO.File]::WriteAllText("$PWD\config.json", [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($r.content)))

# tree listing, then filter locally (one request instead of hundreds)
(Invoke-RestMethod 'https://api.github.com/repos/PasevSU/HASH_REPORT_ENTERPRICE/git/trees/main?recursive=1').tree |
  Where-Object { $_.path -like 'js/*' } | Select-Object path, size
```

With the GitHub CLI the same reads need no token plumbing:

```powershell
gh api repos/PasevSU/HASH_REPORT_ENTERPRICE/contents/js/api.mjs --jq '.sha'
gh release download chronoseal-v5.10.0-cli --pattern '*.zip' -D .
```

### Running the clone you downloaded

The clone is dependency-free JavaScript: no `npm install`, no Python, no
`node_modules`. Copy these paths out of a checkout or an archive and it runs,
because every path is resolved relative to the file that reads it:

```
js/                                  CLI, programmatic API, PDF layer, tests
tools/                               file filters and the PDF/A-2b normaliser
config/config.json                   required - archive folder, retention, defaults
hash_report_generator/style/         PDF layout rules (33 rule files)
hash_report_generator/report_profiles/
hash_report_generator/modules/
```

That set is about 1.3 MB; Node >= 22.12.0 is the only requirement. A consumer
script, run from anywhere:

```js
import path from 'node:path';
import { reportForFolder, reportForFile, reportForFiles } from './js/api.mjs';

const folder = await reportForFolder('./case', { archive: false, profile: 'combo' });
const single = await reportForFile('./case/scan.pdf', { archive: false, profile: 'single_pdf', embedPdf: true });
const batch = await reportForFiles(['./case/a.eml', './case/b.eml'], { archive: false, perFile: true });

console.log(folder.exitCode, path.basename(String(folder.published)));
```

Each call returns `{ exitCode, summary, layout, published, evidenceDirectory, archive }`,
so callers never parse console text. `reportForFile` takes exactly one file and
`reportForFiles` gives every file its own report, report number and archive row. The
API enforces two rules callers should expect: a generated report is never accepted as
input (the evidence set must not grow with the program's own output), and
`--embed-pdf` accepts exactly one PDF: with no value it embeds the single input file
(`single_pdf`), with a path it embeds that file into a combo report (`combo_pdf`,
`combo_all_pdf` when recursive). `--embed-position before|after` decides whether the
embedded pages come first or last.

Two version numbers appear in the output, and they move independently.
`package.json` and `chronoseal/branding.py` carry the product version (5.10.0-cli in
this release); `js/cli.mjs` exports `CLONE_VERSION` (1.0.0), the version of the
JavaScript re-implementation, which `--version` prints and which is stamped into
the `implementation: chronoseal-js-clone/1.0.0` field of every report the clone
writes. A product release can ship the same clone, and the clone can be fixed
without reissuing the product.

As a package-manager source it also works - the name is `chronoseal-python-rfc3161-addon`
(the root manifest is `private`, so it is not on npm, but `file:` and `github:` sources
resolve). The example pins the release tag so the build is reproducible:

```powershell
npm install github:PasevSU/HASH_REPORT_ENTERPRICE#chronoseal-v5.10.0-cli --no-audit --no-fund
```

```js
import { reportForFolder } from 'chronoseal-python-rfc3161-addon/js/api.mjs';
```

Be aware that a `github:` install clones the whole history - the pack is roughly
350 MB, while `js/` plus `tools/` are 0.4 MB. For a small footprint clone only what
you need:

```powershell
git clone --filter=blob:none --sparse https://github.com/PasevSU/HASH_REPORT_ENTERPRICE.git
cd HASH_REPORT_ENTERPRICE
git sparse-checkout set js tools config hash_report_generator
```

### What GitHub cannot do here

* **Generate a report.** No workflow, action or webhook turns a case folder into a
  PDF; the hashing, the PDF layer and the normaliser all run locally. Publishing a
  CI job that generated real reports would also mean publishing evidence, which this
  project forbids.
* **Store or receive evidence.** There is no upload endpoint. Pushing to the
  repository needs a token with `contents: write` and is a deliberate human act; the
  repository ships the tool, never the evidence.
* **Sign, seal or time-stamp.** The clone has no TSA client. Its signature rows read
  `NOT APPLIED`, `NOT VERIFIED`, `NOT SEALED` by design; trust material lives in
  `trust/` for verification only.
* **Serve a menu.** `js\HashReport.bat` is a Windows launcher for a local menu; the
  CLI and the API are cross-platform.

### Limits worth knowing

* Unauthenticated REST is 60 requests per hour per IP; a token raises it to 5000.
  Reads of `raw.githubusercontent.com` are not counted against that budget.
* The contents API returns files up to 1 MB inline; larger blobs need either the raw
  URL or `/git/blobs/{sha}` (base64, up to 100 MB).
* Anything read from `main` is a moving target - pin a tag or a commit sha when the
  consumer has to be reproducible.

The internal API, the six report types and the three-pass hashing are described in
[docu/JS_CLONE_BG.md](docu/JS_CLONE_BG.md).

## Security and privacy

Read [SECURITY.md](SECURITY.md) before publishing anything from this project.

A hash-report tool handles real case material, so the repository is kept clean by
construction:

* no evidence database (`*.sqlite3`), no archive folder, no generated report,
* no local virtualenv, no `node_modules`, no packed snapshot (`*.7z`, `*.zip`),
* no real case file, no personal name, no scan output,
* no private key material, no token, no credential,
* no tracked file larger than 50 MB,
* a CI guard (`.github/workflows/repo-guard.yml`) fails the build when any of the
  above is committed by accident.

Generate your own evidence locally. This repository ships the tool, never the
evidence.

## Licence

Proprietary, all rights reserved. See [LICENSE](LICENSE). Use is permitted only
with a written authorisation from the copyright holder; redistribution, resale
and publishing of modified copies are not permitted.