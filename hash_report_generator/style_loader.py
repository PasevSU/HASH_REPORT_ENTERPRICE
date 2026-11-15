"""Dynamic, deterministic style loader. Loads every *.js in style/, recursively.
No explicit file list. Unknown or malformed files fail closed. No executable Python styles.

The merged result is cached per process and returned as a deep copy, so repeated
loads (the generator asks four times per run) cost no network I/O while no
consumer can see another consumer's mutations. Every generation runs in its own
child process, and :func:`invalidate` is available for a long-lived process that
edits rules in place. Measurements: docu/V90_JS_CAPABILITY_ANALYSIS_BG.md.
"""
import os
from pathlib import Path
from copy import deepcopy

STYLE_DIR = Path(__file__).resolve().parent / "style"
REQUIRED = frozenset({"PAGE", "COLORS", "FONTS", "LEADING", "TABLE", "COLUMNS", "OBJECTS", "LEGAL_CONTAINER", "KEY_VALUE", "SIZE_UNIT", "TITLE_HIERARCHY", "FONT_FAMILIES", "FONT_FILES", "FONT_POLICY", "BRIDGE_LAYOUT", "REPORT_BLOCK_CONTRACT"})

_CACHE = {}

def _merge(target, source, origin):
    for key, value in source.items():
        if key in target:
            if isinstance(target[key], dict) and isinstance(value, dict):
                _merge(target[key], value, origin)
            else:
                raise ValueError(f"Duplicate style rule {key!r} in {origin}")
        else:
            target[key] = deepcopy(value)

def invalidate(directory=None, pattern="*.js"):
    """Drop the cached result for one rule directory (or all of them)."""
    if directory is None and pattern == "*.js":
        _CACHE.clear()
        return
    folder = Path(directory) if directory is not None else STYLE_DIR
    _CACHE.pop((os.fspath(folder), pattern, directory is None), None)

def _load(folder, pattern, directory):
    if not folder.is_dir():
        raise FileNotFoundError(f"Style directory missing: {folder}")
    result = {}
    files = sorted(p for p in folder.rglob(pattern) if p.is_file() and not p.name.startswith('.'))
    if not files:
        raise ValueError(f"No style definitions found in {folder}")
    try:
        from .js_rules import read_js_rules
    except ImportError:
        from js_rules import read_js_rules
    for path, document in zip(files, read_js_rules(folder, files)):
        if not isinstance(document, dict):
            raise ValueError(f"Style root must be an object: {path}")
        _merge(result, document, str(path))
    if directory is None:
        missing = REQUIRED - result.keys()
        if missing:
            raise ValueError(f"Missing mandatory style sections: {sorted(missing)}")
    return result

def load_styles(directory=None, pattern="*.js"):
    folder = Path(directory) if directory is not None else STYLE_DIR
    key = (os.fspath(folder), pattern, directory is None)
    cached = _CACHE.get(key)
    if cached is None:
        cached = _load(folder, pattern, directory)
        _CACHE[key] = cached
    return deepcopy(cached)
