"""Resilient Tk bootstrap.

Tcl loads its own library scripts (``init.tcl``, ``tk.tcl`` and the ``ttk``
package) the first time an interpreter is created.  On machines where that
first read is disturbed -- most often a virus scanner holding the freshly
touched ``.tcl`` files -- the load aborts with::

    Can't find a usable tk.tcl ...
    couldn't read file ".../tk8.6/ttk/entry.tcl": no such file or directory

The same disturbance can also abort halfway, leaving the interpreter without the
commands that ``init.tcl`` is supposed to define::

    _tkinter.TclError: invalid command name "tcl_findLibrary"

Both symptoms mean "Tcl could not read its own library this time", so both are
retried.

The files are present and readable a moment later, so a short retry succeeds.
Retrying also keeps the failure from surfacing as a crash at launch, and the
second attempt passes the library locations explicitly so that Tcl no longer
has to discover them.
"""
from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from pathlib import Path

LIBRARY_ERROR_MARKERS = (
    "Can't find a usable",
    "This probably means that Tcl wasn't installed properly",
    "couldn't read file",
    # init.tcl aborted half way: the interpreter exists but its commands do not.
    'invalid command name "tcl_findLibrary"',
    'invalid command name "tclIndex"',
)

DEFAULT_ATTEMPTS = 5
DEFAULT_DELAY = 0.2


def is_library_error(exc):
    """True when *exc* is Tcl failing to read its own library scripts."""
    text = str(exc)
    return any(marker in text for marker in LIBRARY_ERROR_MARKERS)


def library_candidates():
    """``(tcl_dir, tk_dir)`` pairs that hold a complete Tcl/Tk script set."""
    bases = []
    for base in (getattr(sys, "base_prefix", ""), sys.prefix, sys.exec_prefix):
        if base:
            bases.append(Path(base) / "tcl")
    try:
        bases.append(Path(sys.executable).resolve().parent.parent / "tcl")
    except OSError:
        pass

    found = []
    seen = set()
    for root in bases:
        tcl_dir = root / "tcl8.6"
        tk_dir = root / "tk8.6"
        key = (str(tcl_dir).lower(), str(tk_dir).lower())
        if key in seen:
            continue
        seen.add(key)
        try:
            if (tcl_dir / "init.tcl").is_file() and (tk_dir / "tk.tcl").is_file():
                found.append((tcl_dir, tk_dir))
        except OSError:
            continue
    return found


def apply_library_hints():
    """Point TCL_LIBRARY/TK_LIBRARY at a complete script set.

    Returns the pair that was applied, or ``None`` when nothing usable was
    found.  An existing setting is respected when it is complete.
    """
    current_tcl = os.environ.get("TCL_LIBRARY")
    current_tk = os.environ.get("TK_LIBRARY")
    if current_tcl and current_tk:
        try:
            if (Path(current_tcl) / "init.tcl").is_file() and (Path(current_tk) / "tk.tcl").is_file():
                return (current_tcl, current_tk)
        except OSError:
            pass

    for tcl_dir, tk_dir in library_candidates():
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
        os.environ["TK_LIBRARY"] = str(tk_dir)
        return (str(tcl_dir), str(tk_dir))
    return None


def init_root(instance, attempts=DEFAULT_ATTEMPTS, delay=DEFAULT_DELAY):
    """Initialise *instance* as a Tk root, retrying a transient library error."""
    last = None
    for attempt in range(max(1, attempts)):
        try:
            tk.Tk.__init__(instance)
            return instance
        except tk.TclError as exc:
            if not is_library_error(exc):
                raise
            last = exc
            apply_library_hints()
            if attempt + 1 < attempts:
                time.sleep(delay * (attempt + 1))
    raise last


def create_root(attempts=DEFAULT_ATTEMPTS, delay=DEFAULT_DELAY):
    """Create a Tk root with the same retry policy as :func:`init_root`."""
    last = None
    for attempt in range(max(1, attempts)):
        try:
            return tk.Tk()
        except tk.TclError as exc:
            if not is_library_error(exc):
                raise
            last = exc
            apply_library_hints()
            if attempt + 1 < attempts:
                time.sleep(delay * (attempt + 1))
    raise last
