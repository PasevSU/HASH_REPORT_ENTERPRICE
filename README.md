# ChronoSeal - HASH_REPORT_ENTERPRICE

ChronoSeal turns a folder into verifiable evidence. It hashes every file the
operator selected, builds one combined PDF report, seals it with an RFC 3161
time-stamp and archives the case in a local SQLite database, so the state of that
folder can still be proven later, on another machine, without the original data.

|  |  |
|---|---|
| Version | 5.5.1 |
| Platform | Windows 10 / 11 (x64) |
| Runtime | Python 3.12+ and Node.js 22.12+ |
| Interface | Tkinter desktop GUI (5 pages) and a headless CLI |
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
```

`Start_ChronoSeal.bat` starts `ChronoSeal_GUI.pyw` with `pythonw.exe`. If
PySide6/Tk material or any dependency is missing, `bootstrap.py` shows a native
preflight window listing the state of every required component and offers an
explicitly approved installation into `.chronoseal-venv`. Nothing is downloaded
or installed without that confirmation, and no browser, WebView or HTTP channel
is used for the interface.

## The five pages

| Page | Name | Purpose |
|---|---|---|
| 01 | Report & TSA | Generate, seal and verify a report |
| 02 | Automation | Plan recurring reports |
| 03 | Settings & Trust | Tool paths and time-stamp profiles |
| 04 | Diagnostics | Preflight checks and evidence logs |
| 05 | Selection | Pick a folder and filter evidence by file type |

Pages are reachable with `Ctrl+1` .. `Ctrl+5` and with the left navigation rail.
Navigation labels, Treeview headings and status lines follow the selected
language (Bulgarian, English, German).

## Selection panel (page 05)

Page 05 is the scoped entry point for one evidence set:

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
338 passed, 11 subtests passed   (269.38 s)
 33 passed   UI acceptance, every step driven through Tk widgets only
 21 passed   JS rule loader and style cache contract
```

The UI acceptance suite drives the real widgets for all five pages and is the
only path used to validate the interface; `docu/V89_UI_TEST_REPORT_BG.md`
records every iteration, including the failures that were fixed.

## Repository layout

```
ChronoSeal_GUI.pyw            GUI entry point (Tkinter)
chronoseal_cli.py             headless entry point
chronoseal/                   pipeline, settings, self-heal, Tk bootstrap, i18n
hash_report_generator/        generator, JS rule loader, file filters, tests
automation/                   automation window and the Selection panel
tests/                        integration, hardening, UI acceptance suites
ui/                           static preview of the Selection panel
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

These documents are written in Bulgarian because they are the working record of
the project; the code, the comments and this README are in English.

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