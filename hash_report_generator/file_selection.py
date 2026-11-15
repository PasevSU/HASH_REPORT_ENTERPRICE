#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.2 - explicit file selection shared by the GUI, the pipeline and the generator.

The operator may name the *exact* evidence files instead of describing a folder
with type filters. The selection travels between processes through one
environment variable (``CHRONOSEAL_EXPLICIT_FILES``) holding a JSON array of
absolute paths, exactly like ``CHRONOSEAL_INCLUDE_PATTERNS`` carries the filters,
so ``hash_report_combined.py`` stays a stand-alone script with no ChronoSeal
imports.

Contract
--------
* An empty selection means "no explicit selection": folder discovery runs and
  every previous behaviour is reproduced byte for byte.
* Paths are expanded, made absolute and de-duplicated case-insensitively on
  Windows while preserving the operator's order.
* :func:`root` is the deepest folder that contains every selected file, so the
  relative paths printed in the report stay unambiguous.
* A selection is never widened: a path that is not a readable regular file is
  reported by :func:`missing` and the caller must fail closed.

This module deliberately has no dependencies outside the standard library.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ENV_FILES = "CHRONOSEAL_EXPLICIT_FILES"
MAX_FILES = 20000


def parse(values):
    """Return the selection as an ordered list of absolute ``Path`` objects."""
    if values is None:
        return []
    if isinstance(values, Path):
        values = [values]
    elif isinstance(values, bytes):
        values = [os.fsdecode(values)]
    elif isinstance(values, str):
        values = _decode(values)
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise ValueError("An explicit file selection must be a path, a list of paths or a JSON array.")
    ordered = []
    seen = set()
    for item in values:
        if item is None or (isinstance(item, str) and not item.strip()):
            continue
        path = Path(os.fsdecode(item)).expanduser()
        try:
            path = path.resolve()
        except OSError as exc:
            raise ValueError(f"Cannot resolve selected file {item!r}: {exc}") from exc
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
        if len(ordered) > MAX_FILES:
            raise ValueError(f"Too many selected files (limit {MAX_FILES}).")
    return ordered


def _decode(value):
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            loaded = json.loads(text)
        except ValueError as exc:
            raise ValueError(f"{ENV_FILES} is not valid JSON: {exc}") from exc
        if not isinstance(loaded, list):
            raise ValueError(f"{ENV_FILES} must hold a JSON array of paths.")
        return loaded
    return [text]


def from_env(environ=None):
    """Read the selection published for a child process (empty when unset)."""
    source = os.environ if environ is None else environ
    return parse(source.get(ENV_FILES))


def to_env(values):
    """Serialise a selection for the child process environment."""
    return json.dumps([str(path) for path in parse(values)], ensure_ascii=False)


def missing(values):
    """Paths that are not readable regular files, in the operator's order."""
    return [path for path in parse(values) if not path.is_file()]


def root(values):
    """Deepest folder containing every selected file."""
    items = parse(values)
    if not items:
        raise ValueError("The file selection is empty, so it has no common root folder.")
    parents = [str(path.parent) for path in items]
    try:
        common = os.path.commonpath(parents)
    except ValueError as exc:
        raise ValueError(
            "All selected files must live on one drive: " + str(exc)) from exc
    return Path(common).resolve()


def relative(values, base=None):
    """Map each resolved path *string* to the POSIX name used in the report.

    The keys are strings, never ``Path`` objects: this mapping is written
    straight into JSON evidence manifests, and ``json.dumps`` rejects
    non-string keys with ``TypeError: keys must be str, int, float, bool
    or None``.
    """
    items = parse(values)
    if not items:
        return {}
    base = Path(base).resolve() if base is not None else root(items)
    mapping = {}
    for path in items:
        try:
            mapping[str(path)] = path.relative_to(base).as_posix()
        except ValueError:
            # A file outside the anchor folder keeps an unambiguous absolute name
            # instead of a bare basename that could collide with another entry.
            mapping[str(path)] = path.as_posix().lstrip("/")
    return mapping


def entries(values, base=None):
    """Selection as ``{'path', 'rel_path'}`` records, in the operator's order."""
    items = parse(values)
    mapping = relative(items, base)
    return [{"path": str(path), "rel_path": mapping[str(path)]} for path in items]


def describe(values):
    """One human-readable line for logs and manifests."""
    items = parse(values)
    if not items:
        return "no explicit file selection"
    names = ", ".join(path.name for path in items[:5])
    if len(items) > 5:
        names += f" and {len(items) - 5} more"
    return f"{len(items)} explicitly selected file(s): {names}"


def audit_payload(values):
    """Machine-readable record of the selection for evidence manifests."""
    items = parse(values)
    if not items:
        return {"explicit_selection": False}
    mapping = relative(items)
    return {
        "explicit_selection": True,
        "selection_root": str(root(items)),
        "selection_count": len(items),
        "selection_files": [
            {"path": str(path), "rel_path": mapping[str(path)]} for path in items
        ],
    }