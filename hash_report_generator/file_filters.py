#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.0 — chainable file-type filters shared by the GUI and the generator.

One implementation, two callers
───────────────────────────────
The Selection panel must show the operator *exactly* what the generator will
hash. Two independent matchers would drift apart, so both sides import this
module:

    automation/File_Filter_Panel.py   →  matches()  (preview list)
    hash_report_combined.py           →  matches()  (actual evidence set)

Filter grammar
──────────────
* One field = one filter. ``*`` and ``?`` are glob wildcards; ``[abc]`` is a
  character set. ``*`` also crosses ``/``, so ``*eml.pdf`` matches
  ``invoices/2026/scan_0001.eml.pdf``.
* A filter without any wildcard is a case-insensitive **substring** match, so
  ``eml.pdf`` and ``*.pdf`` both work as expected.
* ``.`` and ``;`` split one field into several filters:
  ``*.pdf, *.eml`` is equivalent to two fields.
* Filters combine with **OR**: a file is kept when it matches at least one.
* An empty filter list means *no filtering* — every file is included, which is
  exactly the v5.4.0 behaviour.
* Both the file name and the POSIX-style path relative to the selected root are
  tested, so ``*.pdf`` finds nested PDFs while ``invoices/*`` narrows by folder.

Environment
───────────
    CHRONOSEAL_INCLUDE_PATTERNS      JSON list of filter strings
    CHRONOSEAL_FILTER_CASE_SENSITIVE "1" to make matching case-sensitive
"""

import fnmatch
import json
import os
import re

ENV_FILTERS = 'CHRONOSEAL_INCLUDE_PATTERNS'
ENV_CASE = 'CHRONOSEAL_FILTER_CASE_SENSITIVE'

SPLIT_RE = re.compile(r'[,;\r\n]+')
WILDCARD_RE = re.compile(r'[*?\[\]]')
MAX_FILTER_LENGTH = 512


def normalize(field):
    """Split one UI field into individual filters.

    ``'*.pdf, *.eml'`` → ``['*.pdf', '*.eml']``; ``''`` → ``[]``.
    """
    if field is None:
        return []
    text = str(field)
    if len(text) > MAX_FILTER_LENGTH * 4:
        text = text[:MAX_FILTER_LENGTH * 4]
    out = []
    for chunk in SPLIT_RE.split(text):
        item = chunk.strip()
        if item and len(item) <= MAX_FILTER_LENGTH:
            out.append(item)
    return out


def parse(values):
    """Flatten fields into a de-duplicated, order-preserving filter list."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    seen = set()
    result = []
    for value in values:
        for item in normalize(value):
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
    return result


def case_sensitive():
    return (os.environ.get(ENV_CASE, '').strip().lower() in ('1', 'true', 'yes', 'on'))


def _match_one(candidate, pattern, sensitive):
    if not sensitive:
        candidate = candidate.lower()
        pattern = pattern.lower()
    if WILDCARD_RE.search(pattern):
        return fnmatch.fnmatchcase(candidate, pattern)
    return pattern in candidate


def matches(name, rel_path, filters, sensitive=None):
    """True when ``name``/``rel_path`` is selected by ``filters``.

    ``filters`` must already be a flat list (use :func:`parse`). An empty list
    selects everything.
    """
    items = filters or []
    if not items:
        return True
    if sensitive is None:
        sensitive = case_sensitive()
    candidates = [str(name or '')]
    rel = str(rel_path or '').replace('\\', '/')
    if rel and rel not in candidates:
        candidates.append(rel)
    for pattern in items:
        for candidate in candidates:
            if candidate and _match_one(candidate, pattern, sensitive):
                return True
    return False


def describe(filters):
    """Human/audit string: ``'none'`` when everything is included."""
    items = parse(filters) if filters else []
    return ', '.join(items) if items else 'none'


def from_env():
    """Read the filter list handed over by ``chronoseal.pipeline``."""
    raw = (os.environ.get(ENV_FILTERS) or '').strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return parse(raw)
    if isinstance(value, str):
        return parse(value)
    if isinstance(value, (list, tuple)):
        return parse([str(item) for item in value])
    return []


def to_env(filters):
    """Serialise a filter list for the child-process environment."""
    return json.dumps(parse(filters), ensure_ascii=False)


def audit_payload(filters):
    """Small dict embedded in discovery/manifest evidence for reproducibility."""
    items = parse(filters) if filters else []
    return {
        'filters': items,
        'filter_count': len(items),
        'filter_case_sensitive': case_sensitive(),
        'filter_description': describe(items),
    }
