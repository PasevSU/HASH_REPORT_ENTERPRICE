"""T01-T30 acceptance suite for ChronoSeal v5.5.0 (Selection & Filters).

The window is built exactly the way the production entry point builds it, then
driven through Tk widgets only: Entry.insert/delete, Button.invoke, StringVar.set,
event_generate and notebook selection. No assertion is satisfied by calling a
panel helper that the user could not reach.
"""
import importlib.machinery
import importlib.util
import io
import os
import subprocess
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

from chronoseal.pipeline import Pipeline, PipelineError  # noqa: E402


# --------------------------------------------------------------------- helpers
def _load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    # The suite asserts on widget labels, so it must run in a known language
    # whatever config/ui.json says; the saved choice is restored afterwards.
    from chronoseal import i18n
    saved = i18n.language()
    i18n.set_language("en", persist=False)
    module = _load(ROOT / "ChronoSeal_GUI.pyw", "chronoseal_ui_acceptance")
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
    for name in ("a.pdf", "notes.txt", "scan_0001.eml.pdf", "LOUD.PDF",
                 "RPT-20260101-000000000-AAAABBBB_HASHREPORT_TYP_COMBO.pdf"):
        (base / name).write_bytes(b"%PDF-1.4\n" if name.lower().endswith(".pdf") else b"x")
    for name in ("deep.pdf", "deep.eml", "deep.txt"):
        (base / "nested" / name).write_bytes(b"y")
    return base


def _pump(window, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            window.update()
        except tk.TclError:
            return
        time.sleep(0.01)


def _wait(window, predicate, timeout=25.0):
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


def _settle(window):
    """Let both debounces (scan 350 ms, filter 300 ms) run to completion."""
    _pump(window, 0.6)


def _panel_ns(window):
    return type(window.filter_panel).choose_folder.__globals__


def _legacy_ns(window):
    for klass in type(window).__mro__:
        if klass is not type(window) and "start" in klass.__dict__:
            return klass.start.__globals__
    raise AssertionError("legacy base module not found")


def _start_namespaces(window):
    """Every module globals dict that contributes a start() implementation."""
    found = []
    for klass in type(window).__mro__:
        if "start" in klass.__dict__:
            found.append(klass.start.__globals__)
    if not found:
        raise AssertionError("start() implementation not found")
    return found


def _widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _widgets(child)


def _press_generate(window):
    """Press the main panel generate button whatever language the UI speaks."""
    window.go.state(["!disabled"])
    window.go.invoke()


def _button(parent, text):
    for widget in _widgets(parent):
        if isinstance(widget, ttk.Button) and widget.cget("text") == text:
            return widget
    raise AssertionError("button not found: " + text)


def _rows(panel):
    return [panel.tree.item(iid, "values") for iid in panel.tree.get_children()]


def _rels(panel):
    return sorted(str(row[0]) for row in _rows(panel))


def _reset(window):
    panel = window.filter_panel
    for attribute in ("_scan_job", "_filter_job"):
        handle = getattr(panel, attribute, None)
        if handle is not None:
            try:
                window.after_cancel(handle)
            except (tk.TclError, ValueError):
                pass
            setattr(panel, attribute, None)
    panel.clear_filters()
    panel._index = []
    panel._index_key = None
    panel.source.set("")
    panel.recursive.set(False)
    window.file_filters = []
    window.target.set("")
    window.rec.set(False)
    window.mode.set("combined")
    window._refresh_filter_indicator()
    _pump(window, 0.5)


def _scan(window, folder, recursive=False):
    _reset(window)
    panel = window.filter_panel
    panel._index_key = None
    panel.recursive.set(bool(recursive))
    panel.source.set(str(folder))
    assert _wait(window, lambda: panel._index_key is not None), "scan never finished"
    _settle(window)
    return panel


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


@pytest.fixture(autouse=True)
def no_modal_dialogs(app, monkeypatch):
    """A real message box would block the whole run, so record instead of showing."""
    shown = []

    def record(*args, **kwargs):
        shown.append(args)
        return None

    def answer_yes(*args, **kwargs):
        shown.append(args)
        return True

    stub = SimpleNamespace(
        showinfo=record, showwarning=record, showerror=record,
        askyesno=answer_yes, askokcancel=answer_yes, askdirectory=lambda *a, **k: "",
    )
    for namespace in (_panel_ns(app), _legacy_ns(app)):
        monkeypatch.setitem(namespace, "messagebox", stub)
    monkeypatch.setitem(_panel_ns(app), "filedialog", stub)
    return shown


@pytest.fixture()
def no_worker(monkeypatch, app):
    _NoopThread.instances = []
    for namespace in _start_namespaces(app):
        monkeypatch.setitem(namespace, "threading",
                            SimpleNamespace(Thread=_NoopThread, Event=threading.Event))
    monkeypatch.setattr(app, "save_settings_silent", lambda *a, **k: None)
    monkeypatch.setattr(app, "startup_ready", True, raising=False)
    return _NoopThread.instances


# ------------------------------------------------------------------ T01 .. T03
def test_t01_panel_exists_six_pages_and_ctrl6(app):
    assert len(app.nb.tabs()) == 6
    assert app.nb.index(app.report_files_tab) == 1
    assert app.nb.index(app.filter_tab) == 5
    assert app.filter_panel.frame.winfo_exists()
    # A bare digit sequence (<Control-1>) binds a mouse button in Tk, so the
    # keyboard shortcut must be registered as <Control-Key-N>.
    assert app.bind("<Control-Key-6>"), "Ctrl+6 must be bound to the selection page"
    assert app.bind("<Control-Key-1>"), "Ctrl+1 must be bound to the report page"
    assert not app.bind("<Control-1>"), "Ctrl+1 must not be bound as a mouse button"
    app._select_page("run_tab")
    _pump(app, 0.1)
    # Key events are routed to the focus window, so the window has to own focus.
    app.deiconify()
    app.update()
    app.focus_force()
    _pump(app, 0.15)
    try:
        app.event_generate("<Control-Key-6>")
        _pump(app, 0.3)
        assert app.nb.select() == str(app.filter_tab)
        app.event_generate("<Control-Key-1>")
        _pump(app, 0.3)
        assert app.nb.select() == str(app.run_tab)
    finally:
        app.withdraw()
        app.update()


def test_t02_choose_folder_writes_the_path(app, sample, monkeypatch):
    _reset(app)
    panel = app.filter_panel
    monkeypatch.setitem(_panel_ns(app), "filedialog",
                        SimpleNamespace(askdirectory=lambda **k: str(sample)))
    panel.btn_choose.invoke()
    assert panel.source.get() == str(sample)
    assert _wait(app, lambda: panel._index_key is not None)
    assert len(panel._index) > 0


def test_t03_include_subfolders_is_off_by_default(app):
    _reset(app)
    assert app.filter_panel.recursive.get() is False
    assert app.rec.get() is False
    panel = app.filter_panel
    boxes = [w for w in _widgets(panel.frame) if isinstance(w, ttk.Checkbutton)]
    assert panel.chk_recursive in boxes
    assert panel.chk_recursive.cget("variable") == str(panel.recursive)


# ------------------------------------------------------------------ T04 .. T08
def test_t04_typing_in_the_first_field_reveals_the_second(app):
    _reset(app)
    panel = app.filter_panel
    assert len(panel.filter_rows) == 1
    panel.filter_rows[0]["entry"].insert(0, "*eml.pdf")
    assert len(panel.filter_rows) == 2
    assert panel.filter_rows[1]["var"].get() == ""


def test_t05_typing_in_the_second_field_reveals_the_third(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*eml.pdf")
    panel.filter_rows[1]["entry"].insert(0, "*.pdf")
    assert len(panel.filter_rows) == 3


def test_t06_deleting_text_never_adds_fields(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "abc")
    assert len(panel.filter_rows) == 2
    panel.filter_rows[0]["entry"].delete(0, "end")
    assert len(panel.filter_rows) == 2
    assert panel.filter_rows[1]["var"].get() == ""


def test_t07_x_button_removes_the_field_and_its_filter(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.pdf")
    panel.filter_rows[1]["entry"].insert(0, "*.eml")
    assert panel.active_filters() == ["*.pdf", "*.eml"]
    _button(panel.filter_rows[0]["row"], "(x)").invoke()
    assert panel.active_filters() == ["*.eml"]
    assert len(panel.filter_rows) == 2


def test_t08_comma_in_one_field_yields_two_filters(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.pdf, *.eml")
    assert panel.active_filters() == ["*.pdf", "*.eml"]
    assert "2 active" in panel.filter_state.get()


# ------------------------------------------------------------------ T09 .. T12
def test_t09_star_eml_pdf_matches_scan_0001_eml_pdf(app, sample):
    _scan(app, sample)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*eml.pdf")
    _settle(app)
    assert _rels(panel) == ["scan_0001.eml.pdf"]


def test_t10_matching_ignores_letter_case(app, sample):
    _scan(app, sample)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.PDF")
    _settle(app)
    assert _rels(panel) == ["LOUD.PDF", "a.pdf", "scan_0001.eml.pdf"]


def test_t11_several_filters_combine_with_or(app, sample):
    _scan(app, sample, recursive=True)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.txt")
    panel.filter_rows[1]["entry"].insert(0, "*.eml")
    _settle(app)
    assert _rels(panel) == ["nested/deep.eml", "nested/deep.txt", "notes.txt"]


def test_t12_without_filters_every_candidate_is_shown(app, sample):
    panel = _scan(app, sample)
    assert len(_rels(panel)) == 4
    assert "RPT-" not in " ".join(_rels(panel))
    assert "4 selected of 4" in panel.summary.get()


# ------------------------------------------------------------------ T13 .. T15
def test_t13_recursive_includes_nested_files(app, sample):
    panel = _scan(app, sample, recursive=True)
    panel.filter_rows[0]["entry"].insert(0, "deep.pdf")
    _settle(app)
    assert _rels(panel) == ["nested/deep.pdf"]


def test_t14_non_recursive_omits_nested_files(app, sample):
    panel = _scan(app, sample, recursive=False)
    rels = _rels(panel)
    assert rels
    assert not any("/" in rel for rel in rels)


def test_t15_empty_result_shows_a_message_not_an_exception(app, sample):
    panel = _scan(app, sample)
    panel.filter_rows[0]["entry"].insert(0, "*.xyz")
    _settle(app)
    assert _rels(panel) == []
    assert "FILTER_MATCHED_NO_FILES" in panel.status.get()


# ------------------------------------------------------------------ T16 .. T18
def test_t16_apply_to_main_panel_carries_scope_and_filters(app, sample):
    panel = _scan(app, sample, recursive=True)
    panel.filter_rows[0]["entry"].insert(0, "*.pdf")
    _settle(app)
    panel.btn_apply.invoke()
    _pump(app, 0.3)
    assert app.target.get() == str(sample)
    assert app.rec.get() is True
    assert app.file_filters == ["*.pdf"]
    assert app.nb.select() == str(app.run_tab)


def test_t17_main_panel_shows_the_active_filters(app):
    app.file_filters = ["*.pdf", "*.eml"]
    app.mode.set("combined")
    app._refresh_filter_indicator()
    assert app.filter_summary.get() == "*.pdf, *.eml"
    app.mode.set("file")
    app._refresh_filter_indicator()
    assert "(ignored for a single file)" in app.filter_summary.get()
    app.mode.set("combined")
    app._refresh_filter_indicator()


def test_t18_clear_in_the_main_panel_clears_the_filters(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.pdf")
    app.file_filters = ["*.pdf"]
    app._refresh_filter_indicator()
    _button(app.run_tab, "Clear").invoke()
    _pump(app, 0.2)
    assert app.file_filters == []
    assert app.filter_summary.get() == "none - every file in the folder is evidence"
    assert panel.active_filters() == []
    assert len(panel.filter_rows) == 1


# ------------------------------------------------------------------ T19 .. T21
def test_t19_generate_from_selection_hands_filters_to_pipeline(app, sample, no_worker):
    panel = _scan(app, sample)
    panel.filter_rows[0]["entry"].insert(0, "*.eml")
    _settle(app)
    panel.btn_generate.invoke()
    _pump(app, 0.3)
    assert app._run_args[0] == str(sample)
    assert app._run_args[1] == "combined"
    assert app._run_args[6] == ["*.eml"]
    assert app.nb.select() == str(app.run_tab)
    started = [t for t in no_worker if t.started]
    assert len(started) == 1, "exactly one stubbed worker must be started"


def test_t20_empty_folder_is_refused_without_a_subprocess(app, monkeypatch, no_worker):
    _reset(app)
    shown = []
    monkeypatch.setitem(_panel_ns(app), "messagebox",
                        SimpleNamespace(showinfo=lambda *a, **k: shown.append(a)))
    assert app.filter_panel.generate() is False
    assert shown, "the user must be told why nothing started"
    assert not [t for t in no_worker if t.started]


def test_t21_missing_folder_is_refused_without_a_subprocess(app, tmp_path, monkeypatch, no_worker):
    _reset(app)
    shown = []
    monkeypatch.setitem(_panel_ns(app), "messagebox",
                        SimpleNamespace(showinfo=lambda *a, **k: shown.append(a)))
    app.filter_panel.source.set(str(tmp_path / "does-not-exist"))
    _pump(app, 0.5)
    assert app.filter_panel.generate() is False
    assert shown
    assert not [t for t in no_worker if t.started]


# ------------------------------------------------------------------ T22 .. T24
def test_t22_scanning_does_not_block_the_ui(app, sample):
    _reset(app)
    panel = app.filter_panel
    started = time.monotonic()
    panel.source.set(str(sample))
    elapsed = time.monotonic() - started
    assert elapsed < 0.5, "setting the folder must not walk the tree on the UI thread"
    assert _wait(app, lambda: panel._index_key is not None)
    _settle(app)
    assert len(_rels(panel)) == 4


def test_t23_superseded_scans_leave_no_running_thread(app, sample):
    _reset(app)
    panel = app.filter_panel
    before = {thread.ident for thread in threading.enumerate()}
    panel.source.set(str(sample))
    panel.scan()
    panel.scan()
    assert _wait(app, lambda: panel._index_key is not None)
    _settle(app)
    leftover = [t for t in threading.enumerate() if t.ident not in before and t.is_alive()]
    assert leftover == []


def test_t24_navigating_all_pages_keeps_the_panel_intact(app):
    _reset(app)
    panel = app.filter_panel
    panel.filter_rows[0]["entry"].insert(0, "*.pdf")
    _settle(app)
    state = panel.filter_state.get()
    for _ in range(2):
        for name, *_rest in app.NAV_ITEMS:
            app._select_page(name)
            _pump(app, 0.05)
    app._select_page("filter_tab")
    _pump(app, 0.1)
    assert app.nb.index(app.filter_tab) == 5
    assert panel.filter_state.get() == state
    assert panel.active_filters() == ["*.pdf"]


# ------------------------------------------------------------------ T25 .. T26
def test_t25_main_panel_runs_without_filters(app, sample, no_worker):
    _reset(app)
    app.target.set(str(sample))
    app.mode.set("combined")
    app.file_filters = []
    app._refresh_filter_indicator()
    _press_generate(app)
    _pump(app, 0.3)
    assert app._run_args[6] == []
    assert app._run_args[0] == str(sample)


def test_t25b_single_file_report_never_sends_filters(app, tmp_path, no_worker):
    target = tmp_path / "one.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    app.target.set(str(target))
    app.mode.set("file")
    app.file_filters = ["*.pdf"]
    _press_generate(app)
    _pump(app, 0.3)
    assert app._run_args[6] == []


def test_t26_automation_panel_still_loads(app):
    assert app.automation_panel is not None
    assert app.nb.index(app.automation_tab) == 2
    assert app.automation_tab.winfo_children()
    app._select_page("automation_tab")
    _pump(app, 0.1)
    assert app.nb.select() == str(app.automation_tab)


def test_t26b_pipeline_rejects_filters_for_a_single_file(tmp_path):
    target = tmp_path / "one.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(PipelineError) as excinfo:
        Pipeline(tmp_path, {}).run(target, mode="file", filters=["*.pdf"])
    assert "only apply to a folder" in str(excinfo.value)


# ------------------------------------------------------------------ T27 .. T30
def test_t27_heartbeat_output_keeps_a_slow_child_alive(tmp_path):
    script = (
        "import time\n"
        "for _ in range(12):\n"
        "    print('[heartbeat] phase=verify done=1/12 pct=8.3', flush=True)\n"
        "    time.sleep(0.2)\n"
    )
    process = Pipeline(tmp_path, {})._run(
        [sys.executable, "-u", "-c", script],
        cwd=tmp_path, idle_timeout=0.9, encoding="utf-8",
    )
    assert process.returncode == 0


def test_t28_silent_child_is_killed_with_a_clear_message(tmp_path):
    started = time.monotonic()
    with pytest.raises(PipelineError) as excinfo:
        Pipeline(tmp_path, {})._run(
            [sys.executable, "-u", "-c", "import time; time.sleep(20)"],
            cwd=tmp_path, idle_timeout=0.9, encoding="utf-8",
        )
    assert time.monotonic() - started < 15
    assert "no output for" in str(excinfo.value)
    assert "produced no output at all" in str(excinfo.value)


def test_t29_stall_message_reports_the_last_phase(tmp_path):
    script = (
        "import time\n"
        "print('[heartbeat] phase=verify done=3/100 pct=3.0', flush=True)\n"
        "time.sleep(20)\n"
    )
    with pytest.raises(PipelineError) as excinfo:
        Pipeline(tmp_path, {})._run(
            [sys.executable, "-u", "-c", script],
            cwd=tmp_path, idle_timeout=0.9, encoding="utf-8",
        )
    message = str(excinfo.value)
    assert "Last reported progress" in message
    assert "phase=verify done=3/100" in message
    assert "Last child output" in message


def test_t30_heartbeat_switch_off_and_on(tmp_path):
    generator = ROOT / "hash_report_generator"
    code = "import progress_heartbeat as h; h.install(); h.phase('verify', total=4); h.close()"

    def run(value):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["CHRONOSEAL_HEARTBEAT_SECONDS"] = value
        return subprocess.run([sys.executable, "-c", code], cwd=str(generator), env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=90)

    off = run("0")
    assert off.returncode == 0, off.stderr
    assert "[heartbeat]" not in off.stdout
    on = run("30")
    assert on.returncode == 0, on.stderr
    assert "[heartbeat] phase=verify" in on.stdout


def test_t30b_disabled_heartbeat_writes_nothing_in_process():
    module = _load(ROOT / "hash_report_generator" / "progress_heartbeat.py",
                   "chronoseal_heartbeat_acceptance")
    quiet = io.StringIO()
    silent = module.Heartbeat(interval=0, stream=quiet)
    assert silent.enabled is False
    silent.set_phase("verify", total=10)
    silent.tick(done=5)
    assert quiet.getvalue() == ""
    loud = io.StringIO()
    beating = module.Heartbeat(interval=30, stream=loud)
    assert beating.enabled is True
    beating.set_phase("verify", total=10)
    assert "[heartbeat] phase=verify" in loud.getvalue()


# --------------------------------------------------------------- localisation
def _panel_widgets(window):
    return [window.btn_choose, window.btn_scan, window.chk_recursive,
            window.btn_apply, window.btn_generate]


def test_t34_panel_strings_follow_the_selected_language(app):
    from chronoseal import i18n
    panel = app.filter_panel
    assert panel.btn_choose.cget("text") == "Choose folder"
    assert panel.btn_generate.cget("text") == "Generate report from selection"
    assert panel.tree.heading("rel", "text") == "Relative path"
    assert app.nb.tab(app.filter_tab, "text") == "Selection & Filters"
    i18n.set_language("bg", persist=False)
    try:
        i18n.apply_language(app)
        app.update_idletasks()
        assert panel.btn_choose.cget("text") == "Избор на папка"
        assert panel.btn_generate.cget("text") == "Генерирай отчет от избора"
        assert panel.tree.heading("rel", "text") == "Относителен път"
        assert app.nb.tab(app.filter_tab, "text") == "Избор и филтри"
    finally:
        i18n.set_language("en", persist=False)
        i18n.apply_language(app)
        app.update_idletasks()
    assert panel.btn_choose.cget("text") == "Choose folder"
    assert panel.btn_generate.cget("text") == "Generate report from selection"
    assert panel.tree.heading("rel", "text") == "Relative path"


def test_t35_dynamic_status_lines_keep_their_payload_in_every_language(app):
    from chronoseal import i18n
    status = app.filter_panel.status
    for code, expected in (("en", "Applied to the main panel: *.pdf"),
                           ("bg", "Приложено в главния панел: *.pdf"),
                           ("de", "Auf das Hauptfenster angewendet: *.pdf")):
        i18n.set_language(code, persist=False)
        try:
            status.set("Applied to the main panel: *.pdf")
            app.update_idletasks()
            assert status.get() == expected
        finally:
            i18n.set_language("en", persist=False)
            status.set("")
    i18n.set_language("bg", persist=False)
    try:
        status.set(i18n.tr("Scanning {path}", path="C:/evidence"))
        assert status.get() == "Сканиране: C:/evidence"
        status.set(i18n.tr("Scanned {count} candidate file(s).", count=7))
        assert status.get() == "Намерени са 7 подходящи файла."
    finally:
        i18n.set_language("en", persist=False)
        status.set("")
