# ChronoSeal - HASH_REPORT_ENTERPRICE (GUI edition)

> **GUI edition.** This branch is the desktop release: a Tkinter interface for quick
> actions - pick a file or a folder, get a sealed report - and for sending the result
> by e-mail. Reports carry no QR block and no verification obligation. The CLI
> edition lives on `release/cli`.

ChronoSeal turns a folder into verifiable evidence. It hashes every file the
operator selected, builds one combined PDF report, seals it with an RFC 3161
time-stamp and archives the case in a local SQLite database, so the state of that
folder can still be proven later, on another machine, without the original data.

|  |  |
|---|---|
| Version | 5.11.0-gui |
| Platform | Windows 10 / 11 (x64) |
| Runtime | Python 3.12+ and Node.js 22.12+ |
| Interface | Tkinter desktop GUI (6 pages); the CLI stays available for scripting |
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

The GUI offers the same three controls on the run page; everything rarer -
ERLAEUTERUNG, including subfolders, another output folder - lives in a second
dialog. The two subjects are split on purpose: `PDF embedding…` holds the switch,
the position and the file, `Report options…` holds the rest of the run, and each
window shows a one-line prediction (`COMBO_PDF · before · Anlage.pdf`). One
dialog holding both subjects needed scrolling at 125% scaling and hid the
prediction behind the fold.

The Report from Files page carries the same switch and the same before / after
pair, because a combo report built from an explicit file list is embedded exactly
like a scanned folder (`COMBO_PDF`). Opening `PDF embedding…` there hands the
selection over first, so the dialog and the summary describe the run the button
will start. The web workspace lists all six report types and offers the same
position choice for the ones ending in `_PDF`. Every surface reads its rules from
`chronoseal/embed_options.py`, so the prediction an operator sees and the type the
pipeline publishes cannot drift apart.

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

## The end of the report

Every report closes with the legal declaration and the footer. This is the GUI
release: it is built for quick actions - a file or a folder in, a sealed report out -
and for sending the result by e-mail, so the PDF carries no QR block and no
verification obligation. The evidence case next to the report holds everything a
verifier needs.

## Requirements

| Component | Minimum | Used for |
|---|---|---|
| Python | 3.12 | pipeline, GUI, report generation |
| Node.js | 22.12 | PDF rule engine and the RFC 3161 bridge |
| OpenSSL | 1.1.1 / 3.x | independent time-stamp verification |

`Install_Windows.bat` checks all three, installs `requirements-integration.txt`,
locks and verifies the Node dependency, runs the dependency self-check and then
launches the application.

## Install and launch

```
Install_Windows.bat      # first run on a new machine: verify, install, launch
Start_ChronoSeal.bat     # later runs: launch the GUI
Run_Diagnostics.bat      # full diagnostic sweep, safe to run any time
js\HashReport.bat        # menu launcher for the pure JavaScript clone
```

`Start_ChronoSeal.bat` starts `ChronoSeal_GUI.pyw` with `pythonw.exe`.
`Install_Windows.bat` is the only step that installs anything: it verifies
Python, Node.js and OpenSSL, installs `requirements-integration.txt`, locks and
verifies the Node dependency and runs `chronoseal.selfheal`.
`Run_Diagnostics.bat` reports the state of every required component at any time.
No browser, WebView or HTTP channel is used for the interface.
`js\HashReport.bat` is the launcher of the pure JavaScript clone: it collects the folder, recursion, filter patterns, per-file mode, archive, layout gate, report type, the embedded source PDF, the PDF to include and where that PDF goes (`before` / `after`) in a menu and then calls `node js/cli.mjs`, so it needs Node.js only. See `docu/JS_CLONE_BG.md`.

## The six pages

| Page | Name | Purpose |
|---|---|---|
| 01 | Report & TSA | Generate, seal and verify a report |
| 02 | Report from Files | One combo report from individually chosen files |
| 03 | Automation | Plan recurring reports |
| 04 | Settings & Trust | Tool paths and time-stamp profiles |
| 05 | Diagnostics | Preflight checks and evidence logs |
| 06 | Selection | Pick a folder and filter evidence by file type |

Pages are reachable with `Ctrl+1` .. `Ctrl+6` and with the left navigation rail.
Navigation labels, Treeview headings and status lines follow the selected
language (Bulgarian, English, German).

## Report from Files (page 02)

Page 02 builds one combo report from files chosen one by one, instead of from a
folder scope:

* files can be added from any folder and any number of them can be combined,
* a review window lists every selected file with its relative name, type, size,
  modification time and SHA-256 before anything is sealed,
* the run publishes a single `..._HASHREPORT_TYP_COMBO.pdf` with one evidence
  set, and each chosen file carries its relative name in the manifest.

A file that cannot be read blocks the run before publication, exactly as in the
folder-scoped path: a combo report is never published with missing evidence.
The selection travels to the generator as `CHRONOSEAL_EXPLICIT_FILES` and is
recorded in the manifest as `selection_files`, `selection_paths` and
`selection_root`. File-type filters do not apply here; the equivalent scoped
path is page 06.

## Selection panel (page 06)

Page 06 is the scoped entry point for one evidence set:

* pick a folder, optionally including all subfolders,
* chain file-type filters: a filter is typed as a glob (`*.eml`, `*.pdf`,
  `*eml.pdf`) and, as soon as the field is filled, the next filter field appears
  below it - any number of filters can be chained,
* filters are OR-ed inside one chain and combined with the folder scope, so the
  report covers exactly the files the operator saw in the preview.

When the filters match nothing the run stops with exit code `3`
(`FILTER_MATCHED_NO_FILES`), which is different from a real failure: nothing was
hashed, no report number is consumed, and no report is published. The applied
filter chain is stored in the report and in the evidence manifest, so a reader
can see how the evidence set was built.

Filtering itself lives in `hash_report_generator/file_filters.py` and is tested
without the UI, so the matching rules cannot drift from what the panel shows.

## Headless CLI

```
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
repair policy shared by the GUI and the pipeline, archive atomicity (a published
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
326 tests OK   unittest discover -s tests                       (63.45 s)
133 tests OK   unittest discover -s hash_report_generator/tests  (51.66 s)
 35 passed     UI acceptance, every step driven through Tk widgets only
 21 passed     JS rule loader and style cache contract
 19 passed     brand tokens, glyph geometry, no colour literals in the GUI
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

The UI acceptance suite drives the real widgets for all five pages and is the
only path used to validate the interface; `docu/V89_UI_TEST_REPORT_BG.md`
records every iteration, including the failures that were fixed.

## Brand identity

The interface carries the **ChronoSeal(TM) Enterprise** identity introduced in v5.5.1: navy
`#0B1F3B` primary, blue `#1E64D6` accent, gold `#D4AF37`, `#E6EEF7` background
and white surfaces, with Inter for the interface and Source Sans 3 for documents
(both fall back to Segoe UI / the system mono face when they are not installed).

Every colour, font stack, icon and product string lives in one module,
`chronoseal/branding.py`, read by the desktop workspace, the legacy base theme,
the automation panel, the Selection panel and the static preview in `ui/`. A test
fails if a GUI file reintroduces a local colour literal, so a future surface
cannot drift from the palette.

The **PDF report palette is deliberately untouched**. The report is a forensic
document: its style bundle feeds the golden payload hash, so rebranding it would
invalidate the verification path for reports already issued. Branding stops at
the window frame - see [docu/BRANDING_V551_BG.md](docu/BRANDING_V551_BG.md).

## Repository layout

```
ChronoSeal_GUI.pyw            GUI entry point (Tkinter)
chronoseal_cli.py             headless entry point
chronoseal/                   pipeline, settings, self-heal, Tk bootstrap, i18n,
                              branding (palette, fonts, icons, product strings)
hash_report_generator/        generator, JS rule loader, file filters, tests
automation/                   automation window and the Selection panel
tests/                        integration, hardening, UI acceptance suites
ui/                           static preview of the Selection panel
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
| `docu/BRANDING_V551_BG.md` | interface brand identity: palette, fonts, icons, tests |
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
gh release download chronoseal-v5.11.0-gui --pattern '*.zip' -D .
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
`package.json` and `chronoseal/branding.py` carry the product version (5.11.0-gui in
this release); `js/cli.mjs` exports `CLONE_VERSION` (1.0.0), the version of the
JavaScript re-implementation, which `--version` prints and which is stamped into
the `implementation: chronoseal-js-clone/1.0.0` field of every report the clone
writes. A product release can ship the same clone, and the clone can be fixed
without reissuing the product.

As a package-manager source it also works - the name is `chronoseal-python-rfc3161-addon`
(the root manifest is `private`, so it is not on npm, but `file:` and `github:` sources
resolve). The example pins the release tag so the build is reproducible:

```powershell
npm install github:PasevSU/HASH_REPORT_ENTERPRICE#chronoseal-v5.11.0-gui --no-audit --no-fund
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
* **Serve the GUI.** `js\HashReport.bat` is a Windows launcher for a local menu; the
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