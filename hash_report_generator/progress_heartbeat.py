#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.5.0 — progressive output heartbeat for long, silent generator phases.

Why this module exists
──────────────────────
The pipeline watchdog (``chronoseal.pipeline.Pipeline._run``) kills a child
process when it produces *no output* for ``generator.idle_timeout_seconds``
(default 900 s). Several generator phases are pure computation and used to print
nothing at all:

    discovery  →  verify (re-hash of every file)  →  table  →  doc.build()
    →  RFC 3161 embedding  →  SQLite evidence save

On a large evidence tree (tens of thousands of files) over a slow network share,
the silent verify phase alone exceeds 900 s, so a perfectly healthy run was
killed with ``Child process stalled: no output for 900s``.

The heartbeat writes one short ASCII line at least every ``interval`` seconds
from a daemon thread, so the watchdog can always tell "slow" from "stalled".

Contract
────────
* **Never changes any artefact.** Only ``stdout`` is written. Hash values, file
  order, PDF layout and evidence JSON are untouched.
* **Zero cost per file.** ``tick()`` only increments a counter under a lock;
  the emitting thread does all formatting.
* **Off switch.** ``CHRONOSEAL_HEARTBEAT_SECONDS=0`` restores the exact
  v5.4.0 behaviour (no thread, no output).
* **Stand-alone.** Standard library only; the generator never imports ChronoSeal.

Typical wiring
──────────────
    from progress_heartbeat import install, phase, tick, note, close

    install()                       # once, at the start of the run
    phase('discovery')              # prints immediately
    for entry in walk(...):
        tick()                      # counter only
    phase('verify', total=len(files))
    ...
    close()                         # prints a final summary line

Environment
───────────
    CHRONOSEAL_HEARTBEAT_SECONDS   default 30; 0 disables
"""

import os
import sys
import threading
import time

ENV_INTERVAL = 'CHRONOSEAL_HEARTBEAT_SECONDS'
DEFAULT_INTERVAL = 30.0
MIN_INTERVAL = 1.0
PREFIX = '[heartbeat]'

_ACTIVE = None
_ACTIVE_LOCK = threading.Lock()


def interval_from_env(default=DEFAULT_INTERVAL):
    """Read the configured interval; invalid values fall back to ``default``."""
    raw = (os.environ.get(ENV_INTERVAL) or '').strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return float(default)
    if value <= 0:
        return 0.0
    return max(MIN_INTERVAL, value)


class Heartbeat:
    """Emit a progress line at least every ``interval`` seconds."""

    def __init__(self, interval=None, stream=None):
        self.interval = interval_from_env() if interval is None else max(0.0, float(interval))
        self.stream = stream if stream is not None else sys.stdout
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._started = time.monotonic()
        self._last_emit = 0.0
        self._phase = 'starting'
        self._done = 0
        self._total = None
        self._note = None
        self._emitted = 0

    # ── state ────────────────────────────────────────────────────────────────
    @property
    def enabled(self):
        return self.interval > 0

    def set_phase(self, name, total=None, note=None):
        """Start a new phase. Prints immediately so the watchdog timer resets."""
        with self._lock:
            self._phase = str(name)
            self._total = total if total else None
            self._done = 0
            self._note = None if note is None else str(note)
        self._emit(force=True)
        return self

    def tick(self, done=None, note=None):
        """Advance the counter. Cheap: no formatting, no I/O."""
        with self._lock:
            self._done = done if done is not None else self._done + 1
            if note is not None:
                self._note = str(note)
            overdue = self.enabled and (time.monotonic() - self._last_emit) >= self.interval
        if overdue:
            self._emit(force=True)

    def note(self, text):
        """Print an out-of-band line immediately (used at long single steps)."""
        with self._lock:
            self._note = str(text)
        self._emit(force=True)
        return self

    def snapshot(self):
        with self._lock:
            return {
                'phase': self._phase,
                'done': self._done,
                'total': self._total,
                'note': self._note,
                'elapsed': round(time.monotonic() - self._started, 1),
                'lines': self._emitted,
                'interval': self.interval,
            }

    # ── formatting / output ──────────────────────────────────────────────────
    def _line(self):
        with self._lock:
            phase, done, total, note = self._phase, self._done, self._total, self._note
            elapsed = max(time.monotonic() - self._started, 1e-9)
        parts = ['phase=' + phase, 'done=%d' % done]
        if total:
            parts[-1] = 'done=%d/%d' % (done, total)
            parts.append('pct=%.1f' % (100.0 * done / total))
        parts.append('elapsed=%.0fs' % elapsed)
        if total and done:
            rate = done / elapsed
            parts.append('rate=%.1f/s' % rate)
            parts.append('eta=%.0fs' % (max(total - done, 0) / max(rate, 1e-9)))
        if note:
            parts.append('note=' + str(note).replace('\n', ' ')[:160])
        return PREFIX + ' ' + ' '.join(parts)

    def _write(self, line):
        try:
            self.stream.write(line + '\n')
            self.stream.flush()
            self._emitted += 1
        except (OSError, ValueError, AttributeError):
            pass

    def _emit(self, force=False):
        if not self.enabled:
            return
        now = time.monotonic()
        if not force and (now - self._last_emit) < self.interval:
            return
        self._last_emit = now
        self._write(self._line())

    def _loop(self):
        while not self._stop.wait(0.5):
            if not self.enabled:
                continue
            if (time.monotonic() - self._last_emit) >= self.interval:
                self._emit(force=True)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self):
        if not self.enabled:
            return self
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, name='chronoseal-heartbeat', daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        return self

    def close(self):
        """Stop the thread and print a final ``phase=complete`` line."""
        self.stop()
        if self.enabled:
            with self._lock:
                self._phase = 'complete'
            self._emit(force=True)
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc):
        self.close()
        return False


# ── module-level convenience API ─────────────────────────────────────────────
def install(interval=None, stream=None, autostart=True):
    """Create (or replace) the process-wide heartbeat."""
    global _ACTIVE
    with _ACTIVE_LOCK:
        previous = _ACTIVE
        _ACTIVE = Heartbeat(interval=interval, stream=stream)
        if autostart:
            _ACTIVE.start()
    if previous is not None:
        try:
            previous.stop()
        except Exception:
            pass
    return _ACTIVE


def get(create=True):
    """Return the process-wide heartbeat, creating it lazily when allowed."""
    global _ACTIVE
    with _ACTIVE_LOCK:
        if _ACTIVE is None and create:
            _ACTIVE = Heartbeat()
            _ACTIVE.start()
        return _ACTIVE


def reset():
    """Drop the process-wide heartbeat (used by tests)."""
    global _ACTIVE
    with _ACTIVE_LOCK:
        previous, _ACTIVE = _ACTIVE, None
    if previous is not None:
        try:
            previous.close()
        except Exception:
            pass


def phase(name, total=None, note=None):
    heartbeat = get()
    if heartbeat is not None:
        heartbeat.set_phase(name, total=total, note=note)


def tick(done=None, note=None):
    heartbeat = get()
    if heartbeat is not None:
        heartbeat.tick(done=done, note=note)


def note(text):
    heartbeat = get()
    if heartbeat is not None:
        heartbeat.note(text)


def close():
    heartbeat = get(create=False)
    if heartbeat is not None:
        heartbeat.close()


def snapshot():
    heartbeat = get(create=False)
    return heartbeat.snapshot() if heartbeat is not None else None
