"""Unit tests for the resilient Tk bootstrap (no real Tk window required)."""
import os
import tkinter as tk

import pytest

from chronoseal import tk_support

LIBRARY_MESSAGE = (
    "Can't find a usable tk.tcl in the following directories: \n"
    "    C:/Python/tcl/tk8.6\n"
    "This probably means that Tcl wasn't installed properly."
)


class FakeTk:
    """Stands in for tkinter.Tk and fails a fixed number of times first."""

    calls = 0
    failures = 0
    error = LIBRARY_MESSAGE

    def __init__(self, *args, **kwargs):
        type(self).calls += 1
        if type(self).calls <= type(self).failures:
            raise tk.TclError(type(self).error)


@pytest.fixture()
def fake_tk(monkeypatch):
    FakeTk.calls = 0
    FakeTk.failures = 0
    FakeTk.error = LIBRARY_MESSAGE
    monkeypatch.setattr(tk_support.tk, "Tk", FakeTk)
    monkeypatch.setattr(tk_support, "DEFAULT_DELAY", 0.0)
    return FakeTk


def test_library_error_is_recognised():
    assert tk_support.is_library_error(tk.TclError(LIBRARY_MESSAGE)) is True


def test_unrelated_tcl_error_is_not_a_library_error():
    assert tk_support.is_library_error(tk.TclError("bad window path name")) is False


def test_half_loaded_init_tcl_counts_as_a_library_error():
    # init.tcl aborted half way: Tcl exists but its own commands are missing.
    assert tk_support.is_library_error(tk.TclError('invalid command name "tcl_findLibrary"')) is True
    assert tk_support.is_library_error(tk.TclError('invalid command name "tclIndex"')) is True


def test_library_candidates_are_complete_sets():
    for tcl_dir, tk_dir in tk_support.library_candidates():
        assert (tcl_dir / "init.tcl").is_file()
        assert (tk_dir / "tk.tcl").is_file()


def test_create_root_succeeds_without_retry(fake_tk):
    root = tk_support.create_root()
    assert isinstance(root, FakeTk)
    assert fake_tk.calls == 1


def test_create_root_retries_transient_library_error(fake_tk):
    fake_tk.failures = 2
    root = tk_support.create_root(attempts=5, delay=0)
    assert isinstance(root, FakeTk)
    assert fake_tk.calls == 3


def test_create_root_gives_up_after_attempts(fake_tk):
    fake_tk.failures = 99
    with pytest.raises(tk.TclError) as excinfo:
        tk_support.create_root(attempts=3, delay=0)
    assert tk_support.is_library_error(excinfo.value)
    assert fake_tk.calls == 3


def test_create_root_retries_a_half_loaded_init_tcl(fake_tk):
    fake_tk.failures = 1
    fake_tk.error = 'invalid command name "tcl_findLibrary"'
    root = tk_support.create_root(attempts=3, delay=0)
    assert isinstance(root, FakeTk)
    assert fake_tk.calls == 2


def test_create_root_does_not_retry_other_errors(fake_tk):
    fake_tk.failures = 99
    fake_tk.error = "bad window path name"
    with pytest.raises(tk.TclError):
        tk_support.create_root(attempts=4, delay=0)
    assert fake_tk.calls == 1


def test_apply_library_hints_points_at_a_complete_set(monkeypatch):
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    applied = tk_support.apply_library_hints()
    if not tk_support.library_candidates():
        assert applied is None
        return
    assert applied is not None
    assert os.environ["TCL_LIBRARY"] == applied[0]
    assert os.environ["TK_LIBRARY"] == applied[1]


def test_apply_library_hints_keeps_a_valid_existing_setting(monkeypatch):
    candidates = tk_support.library_candidates()
    if not candidates:
        pytest.skip("no complete Tcl/Tk script set on this machine")
    tcl_dir, tk_dir = candidates[0]
    monkeypatch.setenv("TCL_LIBRARY", str(tcl_dir))
    monkeypatch.setenv("TK_LIBRARY", str(tk_dir))
    assert tk_support.apply_library_hints() == (str(tcl_dir), str(tk_dir))


def test_init_root_initialises_the_instance(fake_tk, monkeypatch):
    class Holder:
        pass

    instance = Holder()
    monkeypatch.setattr(tk_support.tk, "Tk", type("Tk", (), {
        "__init__": lambda self: setattr(self, "ready", True)
    }))
    tk_support.init_root(instance)
    assert instance.ready is True
