# Security policy

ChronoSeal produces evidence. A leak in this repository is therefore a data
protection incident, not a code-hygiene issue. This policy describes what must
never leave a workstation, how to report a vulnerability, and what the
repository itself enforces.

## Supported versions

| Version | Supported |
|---|---|
| 5.5.x | yes - security fixes are shipped here |
| 5.4.x and older | no - upgrade before reporting |

## Reporting a vulnerability

Do not open a public issue for a security defect, and never attach case data,
evidence databases, keys or produced reports to a report.

Report privately through either channel:

* GitHub private vulnerability reporting on this repository
  (**Security** tab, *Report a vulnerability*), or
* a direct message to the copyright holder, PasevSU, on GitHub.

Please include: affected version, the platform, the exact command or page used,
and a minimal reproduction built from synthetic files. Never send real case
material.

Expected handling: acknowledgement within 5 working days, an assessment with a
severity within 10 working days, and a fixed release or a documented mitigation
afterwards. Please allow the fix to be published before disclosing the defect.

## What must never be committed or published

| Category | Examples | Why |
|---|---|---|
| Evidence databases | `*.sqlite3`, `*.db`, `ChronoSeal_Archive/`, `ChronoSeal_Evidence/` | contain the case inventory, paths and digests |
| Generated reports | `RPT-*.pdf`, produced PDFs and manifests | contain file names, paths and personal data |
| Real case material | court documents, contracts, correspondence, scans, **any PDF at the repository root** | personal data of real people |
| Credentials | tokens, passwords, `.env`, `*.der`, `*.p12`, `*.pfx` | direct access risk |
| Private keys | anything containing `BEGIN PRIVATE KEY`, `BEGIN RSA PRIVATE KEY`, `BEGIN OPENSSH PRIVATE KEY` | signing and TSA material |
| Local environments | `.chronoseal-venv/`, `node_modules/`, `vendor/` payloads | thousands of files, no review value |
| Snapshots | `*.7z`, `*.zip`, `*.bak`, `*.tar`, `*.gz` | bypass review and the file-size limit |
| Large files | anything above 50 MB | GitHub rejects it, and it is never needed |

Public CA and TSA certificates under `trust/` are deliberately published: they
are public material and are needed to verify a time-stamp independently. A
certificate is not a key - publishing `.pem` files is only acceptable when they
contain a certificate and no private key.

## Repository defences

Three layers keep the list above true, in this order:

1. **`.gitignore`** - blocks the paths and extensions above before staging, so a
   stray build artifact or a local virtualenv cannot be added by accident.
2. **`.github/workflows/repo-guard.yml`** - runs on every push and pull request
   and fails when a tracked file is above 50 MB, matches a forbidden path or
   extension, contains private key material, or contains a token pattern.
3. **Release assets are built from the published tree** - `git archive
   origin/main`, so an archive can only ever contain files the guard already
   accepted. Third-party or artificially generated fixtures stay under
   `qualification/` and `migration_kit/`; nothing is added to an archive by hand.

A release asset is covered by exactly the same rules as the repository. An
archive that predates a rule must be rebuilt, not exempted.

## Handling a machine that ran a case

The archive database, the evidence folders and the session logs stay on the
machine or the share that produced them. Back them up with your own custody
procedure; do not move them into source control, a chat, a ticket or a release.

## Configuration hardening

* `repair.allow_network` stays `false` unless an operator explicitly approves a
  network repair. An evidence tool must not pull code from PyPI or npm silently.
* `rfc3161.require_distinct_providers` and `rfc3161.require_qualified_stop` stay
  `true`; a single unqualified time-stamp is not the product's promise.
* `generator.allow_unreadable_files` stays `false` unless the operator accepts a
  documented exclusion. A report that silently omits evidence must never be
  published.
* Keep `trust/` in sync with `config/config.json`; every pinned certificate has a
  recorded SHA-256, and a mismatch is a blocker, not a warning.