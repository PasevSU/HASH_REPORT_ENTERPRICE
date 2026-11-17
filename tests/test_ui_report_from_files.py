"""R01-R15 acceptance suite for the "Report from Files" page.

The window is built the way the entry point builds it and driven through Tk
widgets: filedialog answers are stubbed, buttons are invoked, tree rows are
inspected. Nothing is satisfied by calling a helper the operator cannot reach.

The claim under test is narrow and important: the files shown in the list are the
files that end up in the report, byte for byte, with no folder scan in between.
"""
import hashlib
import importlib.machinery
import importlib.util
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------- helpers
def _load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    from chronoseal import i18n
    saved = i18n.language()
    i18n.set_language("en", persist=False)
    module = _load(ROOT / "ChronoSeal_GUI.pyw", "chronoseal_ui_report_files")
    i18n.set_language("en", persist=False)
    window = module.ChronoSealDesktop(auto_bootstrap=False)
    window.withdraw()
    window.update_idletasks()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass
    i18n.set_language(saved, persist=False)


@pytest.fixture()
def sample(tmp_path):
    base = tmp_path / "evidence"
    (base / "nested").mkdir(parents=True)
    for name in ("a.pdf", "notes.txt", "scan_0001.eml.pdf"):
        (base / name).write_bytes(b"%PDF-1.4\n" if name.endswith(".pdf") else b"alpha")
    for name in ("deep.txt", "deep.pdf"):
        (base / "nested" / name).write_bytes(b"beta")
    return base


def _pump(window, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            window.update()
        except tk.TclError:
            return
        time.sleep(0.01)


def _wait(window, predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        try:
            window.update()
        except tk.TclError:
            return False
        time.sleep(0.01)
    return bool(predicate())


def _widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _widgets(child)


def _button(parent, text):
    for widget in _widgets(parent):
        if isinstance(widget, ttk.Button) and widget.cget("text") == text:
            return widget
    raise AssertionError("button not found: " + text)


def _rows(panel):
    return [panel.tree.item(iid, "values") for iid in panel.tree.get_children()]


def _names(panel):
    return [str(row[1]) for row in _rows(panel)]


def _panel_ns(window):
    return type(window.report_files_panel).choose_root.__globals__


class _NoopThread:
    """Stands in for threading.Thread so start() cannot spawn a real worker."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.daemon = None
        self.started = False
        _NoopThread.instances.append(self)

    def start(self):
        self.started = True

    def join(self, *args, **kwargs):
        return None

    def is_alive(self):
        return False


def _start_namespaces(window):
    found = []
    for klass in type(window).__mro__:
        if "start" in klass.__dict__:
            found.append(klass.start.__globals__)
    if not found:
        raise AssertionError("start() implementation not found")
    return found


def _reset(window):
    panel = window.report_files_panel
    panel.close_window()
    panel.clear_files()
    window.target.set("")
    window.rec.set(False)
    window.mode.set("combined")
    window.file_selection = []
    window.file_filters = []
    window._run_args = None
    window._refresh_filter_indicator()
    _pump(window, 0.1)


@pytest.fixture(autouse=True)
def dialogs(app, monkeypatch):
    """Record instead of showing modals; answer file dialogs from the test."""
    shown = []
    state = {"files": (), "folder": ""}

    def record(*args, **kwargs):
        shown.append(args)
        return None

    def askopenfilenames(**kwargs):
        return tuple(str(path) for path in state["files"])

    def askdirectory(**kwargs):
        return state["folder"]

    stub = SimpleNamespace(
        showinfo=record, showwarning=record, showerror=record,
        askopenfilenames=askopenfilenames, askdirectory=askdirectory,
        asksaveasfilename=lambda **k: "",
    )
    monkeypatch.setitem(_panel_ns(app), "messagebox", stub)
    monkeypatch.setitem(_panel_ns(app), "filedialog", stub)
    _reset(app)
    yield SimpleNamespace(shown=shown, state=state)
    _reset(app)


@pytest.fixture()
def no_worker(app, monkeypatch):
    _NoopThread.instances = []
    for namespace in _start_namespaces(app):
        monkeypatch.setitem(namespace, "threading",
                            SimpleNamespace(Thread=_NoopThread, Event=threading.Event))
    monkeypatch.setattr(app, "save_settings_silent", lambda *a, **k: None)
    return _NoopThread.instances


def _add(app, *paths):
    panel = app.report_files_panel
    panel.add_paths([str(path) for path in paths])
    _pump(app, 0.05)
    return panel


# ------------------------------------------------------------------ R01 .. R03
def test_r01_the_page_sits_second_and_ctrl2_reaches_it(app):
    panel = app.report_files_panel
    assert len(app.nb.tabs()) == 6
    assert app.nb.index(app.report_files_tab) == 1
    assert app.nb.index(app.automation_tab) == 2
    assert panel.frame.winfo_exists()
    label = app.nb.tab(app.nb.tabs()[1], "text")
    assert "files" in label.lower()
    app._select_page("run_tab")
    _pump(app, 0.1)
    app.deiconify()
    app.update()
    app.focus_force()
    _pump(app, 0.15)
    try:
        app.event_generate("<Control-Key-2>")
        _pump(app, 0.3)
        assert app.nb.select() == str(app.report_files_tab)
    finally:
        app.withdraw()
        app.update()


def test_r02_add_files_lists_exactly_the_chosen_files(app, sample, dialogs):
    panel = app.report_files_panel
    dialogs.state["files"] = [sample / "a.pdf", sample / "nested" / "deep.txt"]
    _button(panel.frame, "Add files...").invoke()
    _pump(app, 0.1)
    assert _names(panel) == ["a.pdf", "nested/deep.txt"]
    assert panel.evidence_root.get() == str(sample)
    assert "2 file(s)" in panel.summary.get()
    assert panel.status.get().startswith("Added 2 file(s)")


def test_r03_adding_the_same_file_twice_does_not_duplicate_it(app, sample):
    panel = _add(app, sample / "notes.txt")
    panel.add_paths([str(sample / "notes.txt")])
    _pump(app, 0.05)
    assert _names(panel) == ["notes.txt"]
    assert panel.status.get() == "Those files are already in the selection."


def test_r04_a_rejected_path_is_reported_and_the_rest_is_kept(app, sample):
    panel = app.report_files_panel
    added, rejected = panel.add_paths(
        [str(sample / "a.pdf"), str(sample / "gone.txt")]
    )
    _pump(app, 0.05)
    assert added == 1
    assert len(rejected) == 1 and "gone.txt" in rejected[0]
    assert _names(panel) == ["a.pdf"]
    assert "gone.txt" in panel.status.get()


def test_r05_remove_selected_drops_only_the_highlighted_row(app, sample):
    panel = _add(app, sample / "a.pdf", sample / "notes.txt", sample / "nested" / "deep.txt")
    panel.tree.selection_set("2")
    _button(panel.frame, "Remove selected").invoke()
    _pump(app, 0.1)
    assert _names(panel) == ["a.pdf", "nested/deep.txt"]
    assert panel.status.get().startswith("Removed 1 file(s); 2 remain.")


def test_r06_clear_list_empties_the_selection_and_the_root(app, sample):
    panel = _add(app, sample / "a.pdf")
    _button(panel.frame, "Clear list").invoke()
    _pump(app, 0.1)
    assert _rows(panel) == []
    assert panel.evidence_root.get() == ""
    assert panel.summary.get() == "No files selected."
    assert str(panel.btn_create.cget("state")) == "disabled"
    assert str(panel.btn_preview.cget("state")) == "disabled"


# ------------------------------------------------------------------ R07 .. R09
def test_r07_choose_folder_writes_the_root_and_the_hint(app, sample, dialogs):
    panel = app.report_files_panel
    dialogs.state["folder"] = str(sample)
    _button(panel.frame, "Choose folder").invoke()
    _pump(app, 0.1)
    assert panel.evidence_root.get() == str(sample)
    assert panel.root_hint.get() == f"Relative paths are measured from {sample.resolve()}."
    assert panel.status.get().startswith("Evidence root set to")


def test_r08_derive_folder_uses_the_deepest_common_folder(app, sample):
    panel = _add(app, sample / "nested" / "deep.txt", sample / "nested" / "deep.pdf")
    panel.evidence_root.set("")
    _button(panel.frame, "Derive from files").invoke()
    _pump(app, 0.1)
    assert panel.evidence_root.get() == str(sample / "nested")
    assert panel.status.get().startswith("Evidence root derived from the files")
    assert _names(panel) == ["deep.txt", "deep.pdf"]


def test_r09_a_narrow_root_widens_when_a_file_outside_is_added(app, sample):
    panel = _add(app, sample / "nested" / "deep.txt")
    assert panel.evidence_root.get() == str(sample / "nested")
    panel.add_paths([str(sample / "a.pdf")])
    _pump(app, 0.05)
    assert panel.evidence_root.get() == str(sample)
    assert sorted(_names(panel)) == ["a.pdf", "nested/deep.txt"]


def test_r10_a_typed_root_is_kept_when_it_still_holds_every_file(app, sample):
    panel = app.report_files_panel
    panel.evidence_root.set(str(sample))
    _pump(app, 0.05)
    panel.add_paths([str(sample / "nested" / "deep.txt")])
    _pump(app, 0.05)
    assert panel.evidence_root.get() == str(sample)


# ---------------------------------------------------------------- R11 .. R13
def test_r11_show_in_window_lists_the_files_with_hashes(app, sample):
    panel = _add(app, sample / "a.pdf", sample / "nested" / "deep.txt")
    _button(panel.frame, "Show in window").invoke()
    _pump(app, 0.1)
    window = panel._preview
    assert window is not None and window.winfo_exists()
    assert window.title() == "Selected files - 2"
    tree = panel._preview_tree
    assert len(tree.get_children()) == 2
    first = hashlib.sha256((sample / "a.pdf").read_bytes()).hexdigest()
    second = hashlib.sha256((sample / "nested" / "deep.txt").read_bytes()).hexdigest()
    assert _wait(app, lambda: panel._hashes.get(str(sample / "a.pdf")) == first)
    assert _wait(app, lambda: panel._hashes.get(str(sample / "nested" / "deep.txt")) == second)
    # Repainting is the operator's own path: press the button again and the
    # window shows the digests that were computed in the background.
    _button(panel.frame, "Show in window").invoke()
    _pump(app, 0.1)
    assert tree.set("1", "sha") == first[:16]
    assert tree.set("2", "sha") == second[:16]
    panel.close_window()
    _pump(app, 0.1)
    assert panel._preview is None


def test_r12_an_empty_list_disables_every_action_and_is_refused(app):
    panel = app.report_files_panel
    for button in (panel.btn_check, panel.btn_create, panel.btn_hand,
                   panel.btn_preview, panel.btn_remove, panel.btn_clear):
        assert str(button.cget("state")) == "disabled", "empty selection must not act"
    assert panel.check_selection() is False
    assert panel.problems and "Add at least one file" in panel.problems[0]
    assert panel.status.get() == panel.problems[0]


def test_r13_check_selection_warns_when_a_file_lives_outside_the_root(app, sample, tmp_path):
    panel = app.report_files_panel
    other = tmp_path / "elsewhere"
    other.mkdir()
    stray = other / "stray.txt"
    stray.write_bytes(b"z")
    panel.add_paths([str(sample / "a.pdf"), str(stray)])
    _pump(app, 0.05)
    panel.evidence_root.set(str(sample))
    _pump(app, 0.05)
    assert panel.check_selection() is True
    assert panel.warnings and "outside the evidence root" in panel.warnings[0]
    assert panel.status.get() == panel.warnings[0]


def test_r14_check_selection_passes_and_names_the_evidence_set(app, sample):
    panel = _add(app, sample / "a.pdf", sample / "notes.txt")
    assert panel.check_selection() is True
    assert panel.problems == []
    assert panel.status.get() == "2 file(s) ready - the list is the evidence set."


# ---------------------------------------------------------------- R15 .. R16
def test_r15_hand_over_publishes_the_selection_without_starting(app, sample):
    panel = _add(app, sample / "a.pdf", sample / "nested" / "deep.txt")
    app.file_filters = ["*.pdf"]
    app.rec.set(True)
    _button(panel.frame, "Hand over to Report & TSA").invoke()
    _pump(app, 0.1)
    assert app.target.get() == str(sample)
    assert app.file_filters == []
    assert app.rec.get() is False
    assert app.file_selection == [str(sample / "a.pdf"), str(sample / "nested" / "deep.txt")]
    assert app._run_args is None, "handing over must not start a run"
    assert panel.status.get().startswith("2 file(s) handed over")


def test_r16_create_report_stops_when_startup_is_not_ready(app, sample, dialogs, no_worker):
    panel = _add(app, sample / "a.pdf")
    app.startup_ready = False
    _button(panel.frame, "Create combo report").invoke()
    _pump(app, 0.1)
    assert not no_worker, "no worker may start before qualification"
    assert app.file_selection == [str(sample / "a.pdf")]
    assert dialogs.shown and "Startup qualification has not passed" in dialogs.shown[-1][1]


def test_r17_create_report_hands_the_selection_to_the_pipeline(app, sample, no_worker):
    panel = _add(app, sample / "a.pdf", sample / "nested" / "deep.txt")
    app.startup_ready = True
    _button(panel.frame, "Create combo report").invoke()
    _pump(app, 0.2)
    assert no_worker and no_worker[0].started
    arguments = app._run_args
    assert arguments[0] == str(sample), "the evidence root anchors the case"
    assert arguments[5] is None or str(arguments[5]) != "", "output folder stays optional"
    assert arguments[6] == [], "filters must never travel with a selection"
    assert arguments[7] == [str(sample / "a.pdf"), str(sample / "nested" / "deep.txt")]
    assert app.file_selection == [], "a started run must not leave a stale selection"
    assert panel.status.get().startswith("Combo report started")


# ------------------------------------------------------------ PDF embedding
def _labelled(parent, kind, text):
    for widget in _widgets(parent):
        if not isinstance(widget, kind):
            continue
        try:
            label = widget.cget("text")
        except tk.TclError:
            continue
        if label == text:
            return widget
    raise AssertionError(f"widget not found: {kind.__name__} {text!r}")


@pytest.fixture()
def embed_boxes(app, monkeypatch):
    """The embedding dialog lives in the legacy module; stub its modals too."""
    shown = []

    def record(*args, **kwargs):
        shown.append(args)
        return None

    stub = SimpleNamespace(showinfo=record, showwarning=record, showerror=record)
    monkeypatch.setitem(type(app)._embed_dialog.__globals__, "messagebox", stub)
    return shown


@pytest.fixture()
def clean_embed(app):
    yield
    state = app._embed_vars()
    state["enabled"].set(False)
    state["path"].set("")
    state["position"].set("after")
    app.report_files_panel._refresh_embed_summary()
    _pump(app, 0.05)


def test_r18_the_combo_page_predicts_the_embedded_pdf(app, sample, dialogs, clean_embed):
    panel = _add(app, sample / "a.pdf")
    assert panel.embed_supported, "the page must share the shell's embedding state"
    switch = _labelled(panel.frame, ttk.Checkbutton, "Embed a PDF in this combo report")
    assert "no embedded PDF" in panel.embed_summary.get()
    app._embed_vars()["path"].set(str(sample / "a.pdf"))
    switch.invoke()
    _pump(app, 0.2)
    text = panel.embed_summary.get()
    assert text.startswith("COMBO_PDF"), text
    assert "after" in text and "a.pdf" in text
    assert app._embed_vars()["enabled"].get() is True


def test_r19_the_embedding_dialog_opens_from_the_combo_page(app, sample, dialogs,
                                                            embed_boxes, clean_embed):
    panel = _add(app, sample / "a.pdf", sample / "notes.txt")
    assert panel.open_embed_dialog() is not None
    assert not embed_boxes, "a valid choice must not raise a modal"
    _reset(app)
    assert panel.open_embed_dialog() is None, "an empty list has nothing to embed into"
    assert panel.status.get().startswith("Add the files for the combo report")

    panel = _add(app, sample / "a.pdf", sample / "notes.txt")
    state = app._embed_vars()
    state["enabled"].set(True)
    state["path"].set(str(sample / "a.pdf"))
    dialog = panel.open_embed_dialog()
    assert isinstance(dialog, tk.Toplevel)
    assert app.target.get() == str(sample), "the dialog describes the handed-over combo"
    _labelled(dialog, ttk.Radiobutton, "Before report").invoke()
    _labelled(dialog, ttk.Button, "OK").invoke()
    _pump(app, 0.1)
    assert state["position"].get() == "before"
    assert panel.embed_summary.get() == "COMBO_PDF · before · a.pdf"
    assert not dialog.winfo_exists()


def test_r20_create_report_carries_the_pdf_and_its_position(app, sample, dialogs,
                                                            no_worker, embed_boxes,
                                                            clean_embed):
    panel = _add(app, sample / "a.pdf", sample / "notes.txt")
    state = app._embed_vars()
    state["enabled"].set(True)
    state["path"].set(str(sample / "a.pdf"))
    state["position"].set("before")
    app.startup_ready = True
    _button(panel.frame, "Create combo report").invoke()
    _pump(app, 0.2)
    assert no_worker and no_worker[0].started
    arguments = app._run_args
    assert Path(arguments[8]) == sample / "a.pdf", "the chosen PDF travels with the run"
    assert arguments[9] == "before", "so does the chosen side"
    assert arguments[7] == [str(sample / "a.pdf"), str(sample / "notes.txt")]
    assert arguments[2] is False, "a selection is never recursive"
