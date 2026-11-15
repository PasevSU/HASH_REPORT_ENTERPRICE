"""Load declarative JavaScript rule objects using a bounded, isolated Node VM.
Never load arbitrary JS from untrusted directories. JS is configuration, not plugins.

All filesystem hardening (symlink rejection, realpath, directory boundary,
suffix, size cap, VM sandbox) runs inside the Node runner in a single process.
The Python side only performs I/O-free lexical checks, because a per-file
``is_symlink()``/``resolve(strict=True)``/``is_file()`` sequence costs seconds
per file on a network share while adding no protection the runner does not
already provide. Measurements: docu/V90_JS_CAPABILITY_ANALYSIS_BG.md.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

RUNNER = Path(__file__).resolve().with_name('js_rules_runner.cjs')

_INVALID_PATH_CODES = frozenset({'SYMLINK', 'OUTSIDE', 'SUFFIX'})
_MISSING_FILE_CODES = frozenset({'MISSING_FILE', 'NOT_FILE', 'UNREADABLE'})


def _canonical(path):
    """Absolute, normalized path that never fails on a denied realpath.

    ``Path.resolve(strict=True)`` calls the platform realpath. On hardened
    Windows volumes that call can return ERROR_ACCESS_DENIED even when the file
    itself is readable, which would otherwise take down every consumer of the
    style rules. The lexical fallback still normalizes ``..`` segments, so the
    rule-directory boundary check below remains effective.
    """
    candidate = Path(path)
    try:
        return candidate.resolve(strict=True)
    except OSError:
        return Path(os.path.abspath(os.fspath(candidate)))


def _runner_budget():
    """Outer budget for one Node run (all files, one process)."""
    raw = os.environ.get('CHRONOSEAL_JS_RULE_TIMEOUT', '')
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return value if value > 0 else 30.0


def _runner_failure(exc):
    if isinstance(exc, subprocess.CalledProcessError):
        raw = (exc.stderr or '').strip()
        try:
            payload = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload.get('code'), payload.get('detail')
    return None


def read_js_rules(folder, files):
    folder = _canonical(folder)
    if not folder.is_dir():
        raise ValueError(f'JS rule directory is missing: {folder}')
    base = os.path.abspath(os.fspath(folder))
    normalized_base = os.path.normcase(base)
    paths = []
    for requested in files:
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = folder / candidate
        text = os.path.abspath(os.fspath(candidate))
        # Lexical only: no stat, no resolve. The runner re-checks the real target.
        normalized = os.path.normcase(text)
        if normalized != normalized_base and not normalized.startswith(normalized_base + os.sep):
            raise ValueError(f'Invalid JS rule path: {candidate}')
        if not text.endswith('.js'):
            raise ValueError(f'Invalid JS rule path: {candidate}')
        paths.append(text)
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js is required for *.js rule loading')
    try:
        proc = subprocess.run([node, '--max-old-space-size=64', str(RUNNER)],
            input=json.dumps({'root':base,'files':paths}, ensure_ascii=True),
            text=True, encoding='utf-8', errors='replace', capture_output=True,
            # Every individual rule is bounded by the runner's 1s VM timeout;
            # this outer budget only guards Node startup plus the reads, which
            # can be slow on a cold/AV-scanned volume.
            timeout=_runner_budget(), check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        failure = _runner_failure(exc)
        if failure:
            code, detail = failure
            if code in _INVALID_PATH_CODES:
                raise ValueError(f'Invalid JS rule path: {detail}') from exc
            if code in _MISSING_FILE_CODES:
                raise ValueError(f'JS rule file is missing: {detail}') from exc
            if code == 'MISSING_FOLDER':
                raise ValueError(f'JS rule directory is missing: {detail}') from exc
            if code == 'TOO_LARGE':
                raise ValueError(f'JS rule is too large: {detail}') from exc
        detail = ''
        if isinstance(exc, subprocess.CalledProcessError):
            detail = (exc.stderr or exc.stdout or '').strip()
        raise ValueError(f'JS rules failed to load: {exc}; {detail}') from exc
    try:
        values = json.loads(proc.stdout)
    except ValueError as exc:
        raise ValueError(f'JS rules returned invalid JSON: {exc}') from exc
    if len(values) != len(paths) or not all(isinstance(v,dict) for v in values):
        raise ValueError('Invalid JS rule payload')
    return values
