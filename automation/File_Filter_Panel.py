"""ChronoSeal Selection panel - folder scope + chainable file-type filters.

Additive only: the Report & TSA panel keeps its own state and behaviour. This
panel reuses the generator's own filter grammar (hash_report_generator/
file_filters.py) so the live preview and the hashed evidence set can never
disagree.

Typing into a filter field immediately reveals the next field. An empty field is
ignored, so the panel is usable with zero, one or many patterns.
"""
import os
import re
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
for _path in (str(HERE), str(BASE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from chronoseal import branding, i18n

i18n.install()


def _load_file_filters():
    """Load the shared filter grammar; identical to what the pipeline uses."""
    try:
        from hash_report_generator import file_filters as module
        return module
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chronoseal_file_filters", BASE / "hash_report_generator" / "file_filters.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


file_filters = _load_file_filters()

MAX_PREVIEW_ROWS = 500
SCAN_DEBOUNCE_MS = 350
FILTER_DEBOUNCE_MS = 300

# Mirror of the generator's self-exclusion rule. A preview that counted our own
# reports as evidence would promise a file set the generator will not hash.
_GENERATED = re.compile(
    r"(?:\d{4}-\d{2}-\d{2}-\d{9}_-_)?RPT-\d{8}-\d{9}-[0-9A-Fa-f]{8}"
    r"(?:-HASHREPORT|_HASHREPORT_TYP_(?:COMBO|SINGLE))\.pdf$",
    re.IGNORECASE,
)
_LEGACY = re.compile(r"_hash_report_(?:combined|individual)\.pdf$", re.IGNORECASE)
_EXPLANATORY = re.compile(r"_-_ERLAEUTERUNG\.pdf$", re.IGNORECASE)
_OWN_ARTEFACTS = {
    "discovery-unreadable.json",
    "hash_report_evidence.sqlite3",
    "hash_report_evidence.sqlite3-shm",
    "hash_report_evidence.sqlite3-wal",
    "hash_report_evidence.sqlite3-journal",
}


def is_generated_artefact(name):
    """True for files the generator excludes from its own evidence set."""
    return bool(
        _GENERATED.match(name)
        or _LEGACY.search(name)
        or _EXPLANATORY.search(name)
        or name.lower() in _OWN_ARTEFACTS
    )


class App:
    """Selection workspace: choose a folder, chain filters, preview, hand over."""

    def __init__(self, root, parent=None):
        self.root = root
        self.parent = parent
        self.frame = ttk.Frame(parent if parent is not None else root, padding=0)
        self.frame.pack(fill="both", expand=True)
        self.source = tk.StringVar(value="")
        self.recursive = tk.BooleanVar(value=False)
        self.summary = tk.StringVar(value="No folder selected.")
        self.status = tk.StringVar(value="Ready.")
        self.filter_state = tk.StringVar(value="No file type filter - every file is evidence.")
        self.filter_rows = []
        self._index = []
        self._index_key = None
        self._scan_token = 0
        self._scan_job = None
        self._filter_job = None
        self._poll_job = None
        self._scan_result = None
        self.btn_choose = None
        self.btn_scan = None
        self.chk_recursive = None
        self.btn_apply = None
        self.btn_generate = None
        self._build()
        self._add_filter_row()
        self._refresh_filter_state()
        self.source.trace_add("write", lambda *_a: self._schedule_scan())
        self.recursive.trace_add("write", lambda *_a: self._schedule_scan())

    # ------------------------------------------------------------------ build
    def _build(self):
        page = self.frame
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)

        ttk.Label(page, text="SELECTION", style="Eyebrow.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(page, text="Choose what becomes evidence", style="PageTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        ttk.Label(
            page,
            text="Pick a folder, add file-type filters and see exactly which files a report "
                 "would cover. Nothing is hashed until the report is generated.",
            style="Muted.TLabel", wraplength=980, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(4, 12))

        scope = ttk.LabelFrame(page, text="  1  -  Folder scope  ", style="Panel.TLabelframe")
        scope.grid(row=3, column=0, sticky="ew")
        scope.columnconfigure(0, weight=1)
        row = ttk.Frame(scope)
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.source).grid(row=0, column=0, sticky="ew")
        self.btn_choose = ttk.Button(row, text="Choose folder", command=self.choose_folder)
        self.btn_choose.grid(row=0, column=1, padx=(8, 0))
        self.btn_scan = ttk.Button(row, text="Scan now", command=self.scan)
        self.btn_scan.grid(row=0, column=2, padx=(6, 0))
        options = ttk.Frame(scope)
        options.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.chk_recursive = ttk.Checkbutton(
            options, text="Include subfolders", variable=self.recursive
        )
        self.chk_recursive.pack(side="left")
        ttk.Label(options, textvariable=self.summary, style="Muted.TLabel").pack(
            side="right"
        )

        filters = ttk.LabelFrame(
            page, text="  2  -  File type filters  ", style="Panel.TLabelframe"
        )
        filters.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        filters.columnconfigure(0, weight=1)
        filters.rowconfigure(1, weight=1)
        ttk.Label(
            filters,
            text='One pattern per field, e.g. *eml.pdf or invoices/*. Type into a field and the '
                 'next one appears. Patterns are combined with OR; an empty list means every file.',
            style="Muted.TLabel", wraplength=980, justify="left",
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 4))
        holder = ttk.Frame(filters)
        holder.grid(row=1, column=0, sticky="nsew", padx=10)
        holder.columnconfigure(0, weight=1)
        self.rows_canvas = tk.Canvas(
            holder, highlightthickness=0, height=112, background=branding.PALETTE["surface"], borderwidth=0
        )
        self.rows_canvas.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(holder, orient="vertical", command=self.rows_canvas.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.rows_canvas.configure(yscrollcommand=bar.set)
        self.rows_frame = ttk.Frame(self.rows_canvas)
        self._rows_window = self.rows_canvas.create_window(
            (0, 0), window=self.rows_frame, anchor="nw"
        )
        self.rows_frame.bind(
            "<Configure>",
            lambda _e: self.rows_canvas.configure(scrollregion=self.rows_canvas.bbox("all")),
        )
        self.rows_canvas.bind(
            "<Configure>",
            lambda e: self.rows_canvas.itemconfigure(self._rows_window, width=e.width),
        )
        actions = ttk.Frame(filters)
        actions.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 8))
        ttk.Button(actions, text="Clear filters", command=self.clear_filters).pack(side="left")
        ttk.Button(actions, text="Copy list", command=self.copy_list).pack(side="left", padx=(6, 0))
        ttk.Label(actions, textvariable=self.filter_state, style="Muted.TLabel").pack(
            side="right"
        )

        preview = ttk.LabelFrame(page, text="  3  -  Preview  ", style="Panel.TLabelframe")
        preview.grid(row=5, column=0, sticky="nsew", pady=(12, 0))
        page.rowconfigure(5, weight=1)
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            preview, columns=("rel", "type", "size"), show="headings", height=10
        )
        for column, heading, width, anchor in (
            ("rel", "Relative path", 620, "w"),
            ("type", "Type", 110, "w"),
            ("size", "Size (KB)", 110, "e"),
        ):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor=anchor, stretch=(column == "rel"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(6, 6))
        scroll = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=(6, 6))
        self.tree.configure(yscrollcommand=scroll.set)

        handover = ttk.Frame(page)
        handover.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        handover.columnconfigure(1, weight=1)
        self.btn_apply = ttk.Button(
            handover, text="Apply to main panel", command=self.apply_to_main
        )
        self.btn_apply.grid(row=0, column=0, sticky="w")
        self.btn_generate = ttk.Button(
            handover, text="Generate report from selection", command=self.generate
        )
        self.btn_generate.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(handover, textvariable=self.status, style="Muted.TLabel").grid(
            row=0, column=2, sticky="e"
        )

    # ------------------------------------------------------- chainable filters
    def _add_filter_row(self, value=""):
        var = tk.StringVar(value=value)
        row = ttk.Frame(self.rows_frame)
        row.pack(fill="x", pady=2)
        index = len(self.filter_rows) + 1
        ttk.Label(row, text=f"{index}.", width=3).pack(side="left")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="(x)", width=4, command=lambda v=var: self._remove_filter_row(v)).pack(
            side="left", padx=(6, 0)
        )
        record = {"var": var, "row": row, "entry": entry}
        self.filter_rows.append(record)
        var.trace_add("write", lambda *_a, v=var: self._on_filter_write(v))
        return record

    def _on_filter_write(self, var):
        # A non-empty last field immediately reveals the next field.
        if var.get().strip() and self.filter_rows and self.filter_rows[-1]["var"] is var:
            self._add_filter_row()
        self._refresh_filter_state()

    def _remove_filter_row(self, var):
        if len(self.filter_rows) <= 1:
            for record in self.filter_rows:
                record["var"].set("")
            self._refresh_filter_state()
            return
        for position, record in enumerate(self.filter_rows):
            if record["var"] is var:
                record["row"].destroy()
                del self.filter_rows[position]
                break
        self._renumber_rows()
        self._refresh_filter_state()

    def _renumber_rows(self):
        for position, record in enumerate(self.filter_rows, start=1):
            children = record["row"].winfo_children()
            if children:
                children[0].configure(text=f"{position}.")

    def active_filters(self):
        """The ordered, de-duplicated filter list currently shown in the panel."""
        return file_filters.parse([record["var"].get() for record in self.filter_rows])

    def clear_filters(self):
        for record in self.filter_rows:
            record["row"].destroy()
        self.filter_rows = []
        self._add_filter_row()
        self._refresh_filter_state()
        self.status.set("Filters cleared.")

    def _refresh_filter_state(self):
        filters = self.active_filters()
        if filters:
            self.filter_state.set(f"{len(filters)} active: {file_filters.describe(filters)}")
        else:
            self.filter_state.set("No file type filter - every file is evidence.")
        self._schedule_filter()

    # -------------------------------------------------------------- discovery
    def choose_folder(self):
        chosen = filedialog.askdirectory(parent=self.frame)
        if chosen:
            self.source.set(chosen)
            self.scan()

    def _schedule_scan(self):
        if self._scan_job is not None:
            try:
                self.root.after_cancel(self._scan_job)
            except (tk.TclError, ValueError):
                pass
        self._scan_job = self.root.after(SCAN_DEBOUNCE_MS, self.scan)

    def _schedule_filter(self):
        if self._filter_job is not None:
            try:
                self.root.after_cancel(self._filter_job)
            except (tk.TclError, ValueError):
                pass
        self._filter_job = self.root.after(FILTER_DEBOUNCE_MS, self.apply_filters)

    def scan(self):
        folder = self.source.get().strip()
        target = Path(folder).expanduser() if folder else None
        if target is None or not target.is_dir():
            self.summary.set("No folder selected.")
            self.status.set("Choose an existing folder first.")
            self._index = []
            self._index_key = None
            self.apply_filters()
            return
        self._scan_token += 1
        token = self._scan_token
        recursive = bool(self.recursive.get())
        self._scan_result = None
        self.summary.set("Scanning...")
        self.status.set(i18n.tr("Scanning {path}", path=str(target)))
        threading.Thread(
            target=self._scan_worker, args=(token, target, recursive), daemon=True
        ).start()
        if self._poll_job is None:
            self._poll_job = self.root.after(40, self._poll_scan)

    def _scan_worker(self, token, target, recursive):
        entries, error = [], None
        try:
            entries = self._walk(target, recursive)
        except OSError as exc:
            error = str(exc)
        # Hand the result over instead of touching Tk from this thread: Tk only tolerates
        # being called from the thread that created it.
        self._scan_result = (token, target, recursive, entries, error)

    def _poll_scan(self):
        self._poll_job = None
        result = self._scan_result
        if result is None:
            try:
                self._poll_job = self.root.after(40, self._poll_scan)
            except (tk.TclError, RuntimeError):
                self._poll_job = None
            return
        self._scan_result = None
        self._scan_done(*result)

    def _scan_done(self, token, target, recursive, entries, error):
        if token != self._scan_token:
            return
        self._index = entries
        self._index_key = (str(target), recursive)
        if error:
            self.status.set("Scan failed: " + error)
        else:
            self.status.set(i18n.tr("Scanned {count} candidate file(s).", count=len(entries)))
        self.apply_filters()

    @staticmethod
    def _walk(target, recursive):
        entries = []
        if not recursive:
            for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
                if not entry.is_file() or is_generated_artefact(entry.name):
                    continue
                entries.append(App._record(entry, entry.name))
            return entries
        for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
            dirnames[:] = sorted(
                [d for d in dirnames if not (Path(dirpath) / d).is_symlink()], key=str.lower
            )
            for name in sorted(filenames, key=str.lower):
                candidate = Path(dirpath) / name
                if is_generated_artefact(name):
                    continue
                try:
                    rel = candidate.relative_to(target).as_posix()
                except ValueError:
                    rel = name
                entries.append(App._record(candidate, rel))
        return entries

    @staticmethod
    def _record(path, rel):
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        suffix = path.suffix.lower().lstrip(".")
        return {"name": path.name, "rel": rel, "type": suffix or "none", "size": size}

    # ---------------------------------------------------------------- preview
    def apply_filters(self):
        filters = self.active_filters()
        selected = [
            entry for entry in self._index
            if file_filters.matches(entry["name"], entry["rel"], filters)
        ]
        excluded = len(self._index) - len(selected)
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        for entry in selected[:MAX_PREVIEW_ROWS]:
            self.tree.insert(
                "", "end",
                values=(entry["rel"], entry["type"], f"{entry['size'] / 1024:.1f}"),
            )
        if not self._index:
            self.summary.set("No folder selected." if not self.source.get().strip()
                             else "No candidate files found.")
        else:
            self.summary.set(f"{len(selected)} selected of {len(self._index)} ({excluded} filtered out)")
        if len(selected) > MAX_PREVIEW_ROWS:
            self.status.set(f"Showing the first {MAX_PREVIEW_ROWS} of {len(selected)} file(s).")
        elif filters and not selected:
            self.status.set(
                "FILTER_MATCHED_NO_FILES: these filters match nothing; the generator would refuse."
            )
        return selected

    def selected_entries(self):
        filters = self.active_filters()
        return [
            entry for entry in self._index
            if file_filters.matches(entry["name"], entry["rel"], filters)
        ]

    def copy_list(self):
        entries = self.selected_entries()
        if not entries:
            self.status.set("Nothing to copy.")
            return
        text = "\n".join(entry["rel"] for entry in entries)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            self.status.set("Clipboard unavailable.")
            return
        self.status.set(f"Copied {len(entries)} path(s) to the clipboard.")

    # --------------------------------------------------------------- handover
    def apply_to_main(self):
        target = self.source.get().strip()
        if target:
            self.root.target.set(target)
            self.root.rec.set(bool(self.recursive.get()))
            try:
                self.root._sync_input_mode()
            except (AttributeError, tk.TclError):
                pass
        filters = self.active_filters()
        self.root.file_filters = filters
        refresh = getattr(self.root, "_refresh_filter_indicator", None)
        if callable(refresh):
            try:
                refresh()
            except tk.TclError:
                pass
        self.status.set(
            f"Applied to the main panel: {file_filters.describe(filters)}"
        )
        select = getattr(self.root, "_select_page", None)
        if callable(select):
            try:
                select("run_tab")
            except (AttributeError, tk.TclError):
                pass
        return filters

    def generate(self):
        target = self.source.get().strip()
        if not target or not Path(target).expanduser().is_dir():
            self.status.set("Choose an existing folder first.")
            messagebox.showinfo(
                "ChronoSeal Selection",
                "Choose an existing folder first.\n\n"
                "The generator cannot start without a folder that exists.",
                parent=self.frame,
            )
            return False
        self.apply_to_main()
        if not getattr(self.root, "startup_ready", False):
            messagebox.showinfo(
                "ChronoSeal Selection",
                "Selection applied to the main panel.\n\n"
                "Startup qualification has not passed yet, so the report was not started. "
                "Open Report & TSA and press Generate once qualification passes.",
                parent=self.frame,
            )
            return False
        select = getattr(self.root, "_select_page", None)
        if callable(select):
            select("run_tab")
        self.root.start()
        return True
