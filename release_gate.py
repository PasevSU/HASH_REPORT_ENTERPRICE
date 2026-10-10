#!/usr/bin/env python3
"""Fail-closed release gate for GitSU. Run from project root."""
import json, pathlib, shutil, subprocess, sys, zipfile
root = pathlib.Path(__file__).resolve().parent
app = root / 'data' / 'app'
results = []
def record(name, ok, detail):
    results.append({'check': name, 'status': 'PASS' if ok else 'BLOCKED', 'detail': detail})
for name, command in [('JavaScript syntax', [shutil.which('npm') or 'npm', 'run', 'check']), ('Node test suite', [shutil.which('npm') or 'npm', 'test'])]:
    try:
        p = subprocess.run(command, cwd=app, capture_output=True, text=True, timeout=600)
        record(name, p.returncode == 0, (p.stdout + p.stderr)[-1200:])
    except (OSError, subprocess.TimeoutExpired) as e:
        record(name, False, str(e))
required = ['LICENSE', 'NOTICE', 'gui.py', 'gui.pyw', 'gui.cmd', 'data/app/gui/main.js', 'data/app/gui/github-auth.js', 'data/app/gui/connect.js', 'data/app/gui/git-view.js', 'data/app/gui/repo-lock.js', 'watcher-package/src/gitsu-watcher.ps1', 'watcher-package/src/gitsu-watcher.sh']
missing = [x for x in required if not (root / x).is_file()]
record('Package completeness', not missing, 'Missing: ' + ', '.join(missing) if missing else 'Required core files exist')
# These require external systems/hardware and cannot be waived by unit tests.
for name in ['Windows Electron GUI end-to-end', 'Offline portable runtime', 'Real GitHub PAT + push', 'Home Assistant / HACS installation and update', 'NAS/UNC stress and locked-file tests', 'Crash/power-loss recovery across restart', 'Watcher auto-commit/push end-to-end', 'Dependency license compliance audit']:
    record(name, False, 'Independent execution evidence not supplied')
report = {'product': 'GitSU SUPERUSER', 'candidate': __import__('json').loads((root / 'data/app/package.json').read_text(encoding='utf-8'))['version'], 'release_status': 'PASS' if all(x['status'] == 'PASS' for x in results) else 'BLOCKED', 'checks': results}
out = root / 'RELEASE_GATE_RESULTS.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Release gate: {report['release_status']} | PASS {sum(x['status']=='PASS' for x in results)}/{len(results)}")
print(f'Report: {out}')
sys.exit(0 if report['release_status'] == 'PASS' else 1)
