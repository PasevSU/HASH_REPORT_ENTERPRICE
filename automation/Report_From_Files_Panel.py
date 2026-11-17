"""ChronoSeal Report from files panel - one combo report from individually chosen files.

Additive only: the Report & TSA, Automation and Selection workspaces keep their own
state. This panel names the *exact* evidence files instead of describing a folder,
so no neighbouring file can slip into the report and no evidence file has to be
copied into a staging folder first.

The chosen paths reach the generator through CHRONOSEAL_EXPLICIT_FILES, the same
channel that already carries CHRONOSEAL_INCLUDE_PATTERNS, so the set shown here and
the set that is hashed cannot disagree.

Nothing is hashed here. "Create combo report" hands the selection to the normal
pipeline, which still generates, dual-stamps, re-verifies, archives and publishes.
"""
import hashlib
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
for _path in (str(HERE), str(BASE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from chronoseal import i18n
from chronoseal.embed_options import EmbedOptionError, resolve_embed_options, summary_text

i18n.install()


def _load_file_selection():
    """Load the shared selection grammar; identical to what the pipeline uses."""
    try:
        from hash_report_generator import file_selection as module
        return module
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chronoseal_file_selection", BASE / "hash_report_generator" / "file_selection.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


file_selection = _load_file_selection()

MAX_ROWS = 2000
HASH_CHUNK = 1 << 20


def _size_text(size):
    if size >= 1 << 30:
        return f"{size / 1073741824:.2f} GB"
    if size >= 1 << 20:
        return f"{size / 1048576:.2f} MB"
    if size >= 1 << 10:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _stamp(value):
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def _contains(folder, path):
    """True when ``path`` lives inside ``folder`` (used to keep relative names clean)."""
    try:
        return Path(path).resolve().is_relative_to(Path(folder).resolve())
    except (OSError, ValueError):
        return False


def digest(path):
    """SHA-256 of one file, streamed so a large file never fills memory."""
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class App:
    """Choose exact files, review them in a window, then create one combo report."""

    def __init__(self, root, parent=None):
        self.root = root
        self.parent = parent
        self.frame = ttk.Frame(parent if parent is not None else root, padding=0)
        self.frame.pack(fill="both", expand=True)
        self.evidence_root = tk.StringVar(value="")
        self.root_hint = tk.StringVar(value="")
        self.summary = tk.StringVar(value="No files selected.")
        self.status = tk.StringVar(value="Ready.")
        self.embed_summary = tk.StringVar(value="")
        self.embed_supported = False
        self._embed_state = None
        self.selected_files = []
        self.problems = []
        self.warnings = []
        self.tree = None
        self.btn_add = None
        self.btn_remove = None
        self.btn_clear = None
        self.btn_preview = None
        self.btn_embed = None
        self.btn_check = None
        self.btn_hand = None
        self.btn_create = None
        self._preview = None
        self._preview_tree = None
        self._hashes = {}
        self._hash_thread = None
        self._bind_embed_state()
        self._build()
        self.evidence_root.trace_add("write", lambda *_a: self._refresh_root_hint())
        self._refresh()

    # ------------------------------------------------------------------ build
    def _build(self):
        page = self.frame
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)

        ttk.Label(page, text="REPORT FROM FILES", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(page, text="One combo report from chosen files", style="PageTitle.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        ttk.Label(
            page,
            text="Pick the individual files that belong in the report. The list becomes the "
                 "evidence set exactly as shown: no folder is scanned, no neighbour file is added "
                 "and nothing is copied first. Nothing is hashed until the report is created.",
            style="Muted.TLabel", wraplength=980, justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(4, 12))

        scope = ttk.LabelFrame(page, text="  1  -  Evidence root  ", style="Panel.TLabelframe")
        scope.grid(row=3, column=0, sticky="ew")
        scope.columnconfigure(0, weight=1)
        row = ttk.Frame(scope)
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.evidence_root).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Choose folder", command=self.choose_root).grid(
            row=0, column=1, padx=(8, 0)
        )
        ttk.Button(row, text="Derive from files", command=self.derive_root).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Label(
            scope, textvariable=self.root_hint, style="Muted.TLabel",
            wraplength=980, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        files = ttk.LabelFrame(page, text="  2  -  Selected files  ", style="Panel.TLabelframe")
        files.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        files.columnconfigure(0, weight=1)
        files.rowconfigure(1, weight=1)
        actions = ttk.Frame(files)
        actions.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 6))
        self.btn_add = ttk.Button(actions, text="Add files...", command=self.add_files)
        self.btn_add.pack(side="left")
        self.btn_remove = ttk.Button(
            actions, text="Remove selected", command=self.remove_selected
        )
        self.btn_remove.pack(side="left", padx=(6, 0))
        self.btn_clear = ttk.Button(actions, text="Clear list", command=self.clear_files)
        self.btn_clear.pack(side="left", padx=(6, 0))
        self.btn_preview = ttk.Button(
            actions, text="Show in window", command=self.show_in_window
        )
        self.btn_preview.pack(side="left", padx=(6, 0))
        ttk.Label(actions, textvariable=self.summary, style="Muted.TLabel").pack(side="right")

        holder = ttk.Frame(files)
        holder.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            holder,
            columns=("index", "rel", "type", "size", "modified", "state"),
            show="headings", height=11,
        )
        for column, heading, width, anchor in (
            ("index", "#", 56, "e"),
            ("rel", "Relative path", 560, "w"),
            ("type", "Type", 100, "w"),
            ("size", "Size", 110, "e"),
            ("modified", "Modified", 150, "w"),
            ("state", "State", 110, "w"),
        ):
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=width, anchor=anchor, stretch=(column == "rel"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        # A combo report can carry a PDF exactly like a folder report; the option
        # belongs next to "Create combo report", not on another page. Only the
        # switch and the position stay here - the file itself is chosen in the
        # dialog, so this page keeps one readable row.
        embed = ttk.LabelFrame(
            page, text="  3  -  PDF embedding (optional)  ", style="Panel.TLabelframe"
        )
        embed.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        embed.columnconfigure(4, weight=1)
        state = self._embed_state
        ttk.Checkbutton(
            embed, text="Embed a PDF in this combo report", variable=state["enabled"]
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            embed, text="Before report", value="before", variable=state["position"]
        ).grid(row=0, column=1, padx=(14, 0), sticky="w")
        ttk.Radiobutton(
            embed, text="After report", value="after", variable=state["position"]
        ).grid(row=0, column=2, padx=(10, 0), sticky="w")
        self.btn_embed = ttk.Button(
            embed, text="PDF embedding…", command=self.open_embed_dialog
        )
        self.btn_embed.grid(row=0, column=3, padx=(16, 0), sticky="w")
        ttk.Label(
            embed, textvariable=self.embed_summary, style="Muted.TLabel"
        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))
        handover = ttk.Frame(page)
        handover.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        handover.columnconfigure(2, weight=1)
        self.btn_check = ttk.Button(
            handover, text="Check selection", command=self.check_selection
        )
        self.btn_check.grid(row=0, column=0, sticky="w")
        self.btn_create = ttk.Button(
            handover, text="Create combo report", command=self.create_report
        )
        self.btn_create.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.btn_hand = ttk.Button(
            handover, text="Hand over to Report & TSA", command=self.hand_over
        )
        self.btn_hand.grid(row=0, column=2, sticky="w", padx=(8, 0))
        ttk.Label(handover, textvariable=self.status, style="Muted.TLabel").grid(
            row=0, column=3, sticky="e"
        )

    # ------------------------------------------------------------- embedding
    def _bind_embed_state(self):
        """Reuse the shell's embedding state so both pages describe one run.

        The switch, the position and the chosen PDF are the same variables the
        Report & TSA page writes into ``_run_args``; nothing is duplicated here.
        """
        getter = getattr(self.root, "_embed_vars", None)
        state = None
        if callable(getter):
            try:
                state = getter()
            except tk.TclError:
                state = None
        self.embed_supported = isinstance(state, dict) and "enabled" in state
        if not self.embed_supported:
            state = {
                "enabled": tk.BooleanVar(value=False),
                "path": tk.StringVar(value=""),
                "position": tk.StringVar(value="after"),
            }
        self._embed_state = state
        for key in ("enabled", "path", "position"):
            variable = state.get(key)
            if variable is None:
                continue
            try:
                variable.trace_add("write", lambda *_a: self._refresh_embed_summary())
            except tk.TclError:
                pass
        self._refresh_embed_summary()

    def _refresh_embed_summary(self):
        """Read back what "Create combo report" will do with the PDF."""
        if not self.embed_supported:
            text = "PDF embedding is not available in this window."
            self.embed_summary.set(text)
            return text
        state = self._embed_state
        try:
            resolved = resolve_embed_options(
                enabled=bool(state["enabled"].get()),
                position=state["position"].get(),
                path=state["path"].get(),
                target=self.evidence_root.get(),
                file_list=True,
                recursive=False,
            )
            text = summary_text(resolved)
        except EmbedOptionError as exc:
            text = str(exc)
        self.embed_summary.set(text)
        return text

    def open_embed_dialog(self):
        """Open the shell's PDF-embedding dialog for this page's report."""
        if not self.embed_supported:
            self.status.set("This window cannot edit the PDF embedding options.")
            return None
        opener = getattr(self.root, "_embed_dialog", None)
        if not callable(opener):
            self.status.set("This window cannot edit the PDF embedding options.")
            return None
        # Hand the selection over first: the dialog reads the shell's state, and
        # only a handed-over list makes it describe a combo report of these files.
        if not self.selected_files:
            self.status.set(
                "Add the files for the combo report first, then choose the PDF to embed."
            )
            return None
        self.hand_over()
        try:
            dialog = opener()
        except tk.TclError as exc:
            self.status.set(f"Could not open the PDF embedding options: {exc}")
            return None
        self._refresh_embed_summary()
        if dialog is not None:
            def release(event):
                if event.widget is dialog:
                    self._refresh_embed_summary()
            try:
                dialog.bind("<Destroy>", release, add="+")
            except tk.TclError:
                pass
        return dialog

    # --------------------------------------------------------------- selection
    def anchor(self):
        """The folder that anchors relative paths, the evidence case and the report."""
        typed = self.evidence_root.get().strip()
        if typed:
            try:
                path = Path(typed).expanduser().resolve()
            except OSError:
                return None
            return path if path.is_dir() else None
        if not self.selected_files:
            return None
        try:
            return file_selection.root(self.selected_files)
        except ValueError:
            return None

    def choose_root(self):
        """Pick the evidence root with the folder dialog, like the main panel does."""
        current = self.evidence_root.get().strip()
        options = {"parent": self.frame, "title": "Evidence root folder"}
        start = current or (str(self.anchor()) if self.anchor() is not None else "")
        if start:
            options["initialdir"] = start
        try:
            chosen = filedialog.askdirectory(**options)
        except tk.TclError:
            chosen = ""
        if not chosen:
            return ""
        self.evidence_root.set(chosen)
        self.status.set(f"Evidence root set to {Path(chosen).resolve()}.")
        return chosen

    def derive_root(self):
        """Set the evidence root to the deepest folder that holds every chosen file."""
        if not self.selected_files:
            self.status.set("Add files first - there is nothing to derive the root from.")
            return None
        try:
            derived = file_selection.root(self.selected_files)
        except ValueError as exc:
            self.status.set(f"Cannot derive the evidence root: {exc}")
            return None
        self.evidence_root.set(str(derived))
        self.status.set(f"Evidence root derived from the files: {derived}.")
        return derived

    def entries(self):
        """Display records for the current selection, in the operator's order."""
        anchor = self.anchor()
        try:
            mapping = file_selection.relative(self.selected_files, anchor)
        except ValueError:
            mapping = {}
        records = []
        for position, path in enumerate(self.selected_files, start=1):
            try:
                stat = path.stat()
                size, modified, state = stat.st_size, _stamp(stat.st_mtime), "ready"
            except OSError:
                size, modified, state = 0, "", "MISSING"
            records.append({
                "index": position,
                "path": path,
                "rel": mapping.get(str(path), path.as_posix()),
                "type": path.suffix.lower().lstrip(".") or "none",
                "size": size,
                "modified": modified,
                "state": state,
            })
        return records

    def add_files(self):
        anchor = self.anchor()
        try:
            chosen = filedialog.askopenfilenames(
                parent=self.frame,
                title="Add files to the combo report",
                initialdir=str(anchor) if anchor is not None else None,
            )
        except tk.TclError:
            chosen = ()
        if not chosen:
            return 0
        added, _rejected = self.add_paths(chosen)
        return added

    def add_paths(self, paths):
        """Merge paths into the selection; returns (added, rejected) for the caller."""
        incoming = []
        rejected = []
        for item in paths:
            try:
                parsed = file_selection.parse([item])
            except ValueError as exc:
                rejected.append(f"{item}: {exc}")
                continue
            for path in parsed:
                if path.is_file():
                    incoming.append(path)
                else:
                    rejected.append(f"{path}: not a readable file")
        merged = file_selection.parse(list(self.selected_files) + incoming)
        added = len(merged) - len(self.selected_files)
        self.selected_files = merged
        self._widen_root()
        self._refresh()
        if added and rejected:
            self.status.set(
                f"Added {added} file(s); {len(self.selected_files)} in the selection. "
                f"{len(rejected)} rejected: {rejected[0]}"
            )
        elif added:
            self.status.set(
                f"Added {added} file(s); {len(self.selected_files)} in the selection."
            )
        elif rejected:
            self.status.set(rejected[0])
        else:
            self.status.set("Those files are already in the selection.")
        return added, rejected

    def _widen_root(self):
        """Keep the evidence root above every chosen file so relative names stay clean."""
        if not self.selected_files:
            return
        try:
            derived = file_selection.root(self.selected_files)
        except ValueError:
            return
        current = self.evidence_root.get().strip()
        if not current:
            self.evidence_root.set(str(derived))
            return
        try:
            present = Path(current).expanduser().resolve()
        except OSError:
            self.evidence_root.set(str(derived))
            return
        if not present.is_dir() or any(not _contains(present, path) for path in self.selected_files):
            self.evidence_root.set(str(derived))

    def remove_selected(self):
        try:
            chosen = set(self.tree.selection())
        except (tk.TclError, AttributeError):
            chosen = set()
        if not chosen:
            self.status.set("Select one or more rows first.")
            return 0
        positions = {int(item) for item in chosen if str(item).isdigit()}
        removed = self.drop_positions(positions)
        self.status.set(f"Removed {removed} file(s); {len(self.selected_files)} remain.")
        return removed

    def drop_positions(self, positions):
        """Remove 1-based row numbers; returns how many files were dropped."""
        kept = [
            path for number, path in enumerate(self.selected_files, start=1)
            if number not in positions
        ]
        removed = len(self.selected_files) - len(kept)
        self.selected_files = kept
        self._refresh()
        return removed

    def clear_files(self):
        self.selected_files = []
        self._hashes = {}
        self.evidence_root.set("")
        self.status.set("Selection cleared.")
        self._refresh()
        return []

    # ----------------------------------------------------------------- render
    def _refresh(self):
        records = self.entries()
        if self.tree is not None:
            try:
                self.tree.delete(*self.tree.get_children())
                for record in records:
                    if record["index"] > MAX_ROWS:
                        break
                    self.tree.insert(
                        "", "end", iid=str(record["index"]),
                        values=(
                            record["index"], record["rel"], record["type"],
                            _size_text(record["size"]), record["modified"], record["state"],
                        ),
                    )
            except tk.TclError:
                return records
        total = sum(record["size"] for record in records)
        missing = [record for record in records if record["state"] != "ready"]
        if not records:
            self.summary.set("No files selected.")
        else:
            self.summary.set(f"{len(records)} file(s) - {_size_text(total)}")
            if len(records) > MAX_ROWS:
                self.status.set(
                    f"Showing the first {MAX_ROWS} of {len(records)} file(s); all of them are reported."
                )
            elif missing:
                self.status.set(f"{len(missing)} selected file(s) are no longer readable.")
        self._refresh_root_hint()
        self._sync_buttons()
        self._refresh_embed_summary()
        return records

    def _refresh_root_hint(self):
        typed = self.evidence_root.get().strip()
        if typed:
            try:
                path = Path(typed).expanduser()
            except OSError:
                path = None
            if path is None or not path.is_dir():
                self.root_hint.set(
                    'This folder does not exist. Choose an existing folder or press "Derive from files".'
                )
            else:
                self.root_hint.set(f"Relative paths are measured from {path.resolve()}.")
            return
        if not self.selected_files:
            self.root_hint.set(
                "Optional. When empty, the deepest folder that contains every chosen file is used."
            )
            return
        try:
            self.root_hint.set(f"Derived evidence root: {file_selection.root(self.selected_files)}")
        except ValueError as exc:
            self.root_hint.set(f"Cannot derive the evidence root: {exc}")

    def _sync_buttons(self):
        empty = not self.selected_files
        for button in (
            self.btn_remove, self.btn_clear, self.btn_preview,
            self.btn_check, self.btn_create, self.btn_hand,
        ):
            if button is None:
                continue
            try:
                button.configure(state="disabled" if empty else "normal")
            except tk.TclError:
                pass
        if self.btn_embed is not None:
            # Configuring the embedding does not need a selection yet.
            try:
                self.btn_embed.configure(
                    state="normal" if self.embed_supported else "disabled"
                )
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ window
    def show_in_window(self):
        """Show the chosen files in their own window, with a live SHA-256 column."""
        records = self.entries()
        window = self._preview
        if window is not None:
            try:
                if window.winfo_exists():
                    self._fill_window(records)
                    window.deiconify()
                    window.lift()
                    window.focus_set()
                    return window
            except tk.TclError:
                pass
        window = tk.Toplevel(self.frame)
        window.title(f"Selected files - {len(records)}")
        window.geometry("1120x700")
        window.minsize(760, 420)
        body = ttk.Frame(window, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        ttk.Label(body, text="FILES IN THIS COMBO REPORT", style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        root = self.anchor()
        ttk.Label(
            body,
            text=(f"Evidence root: {root}" if root is not None else "Evidence root: not chosen yet"),
            style="Muted.TLabel", wraplength=1040, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))
        holder = ttk.Frame(body)
        holder.grid(row=2, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            holder,
            columns=("index", "rel", "type", "size", "modified", "sha"),
            show="headings", height=18,
        )
        for column, heading, width, anchor in (
            ("index", "#", 56, "e"),
            ("rel", "Relative path", 480, "w"),
            ("type", "Type", 90, "w"),
            ("size", "Size", 100, "e"),
            ("modified", "Modified", 140, "w"),
            ("sha", "SHA-256 (first 16)", 170, "w"),
        ):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor=anchor, stretch=(column == "rel"))
        tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scroll.set)
        footer = ttk.Frame(body)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Button(footer, text="Copy list", command=self.copy_list).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Save list...", command=self.save_list).grid(
            row=0, column=1, sticky="w", padx=(6, 0)
        )
        ttk.Button(footer, text="Close", command=self.close_window).grid(row=0, column=2, sticky="e")
        self._preview = window
        self._preview_tree = tree
        window.protocol("WM_DELETE_WINDOW", self.close_window)
        self._fill_window(records)
        self._start_hashes()
        return window

    def _fill_window(self, records):
        tree = self._preview_tree
        if tree is None:
            return
        try:
            tree.delete(*tree.get_children())
            for record in records:
                sha = self._hashes.get(str(record["path"]), "")
                tree.insert(
                    "", "end", iid=str(record["index"]),
                    values=(
                        record["index"], record["rel"], record["type"],
                        _size_text(record["size"]), record["modified"],
                        (sha[:16] if sha else ("unreadable" if sha == "" and record["state"] != "ready" else "...")),
                    ),
                )
        except tk.TclError:
            pass

    def close_window(self):
        window, self._preview = self._preview, None
        self._preview_tree = None
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def compute_hashes(self):
        """Synchronous SHA-256 map for the preview window; also used by the tests."""
        result = {}
        for record in self.entries():
            try:
                result[str(record["path"])] = digest(record["path"])
            except OSError:
                result[str(record["path"])] = ""
        return result

    def _start_hashes(self):
        if not self.selected_files:
            return None
        if self._hash_thread is not None and self._hash_thread.is_alive():
            return self._hash_thread
        pending = [
            str(record["path"]) for record in self.entries()
            if str(record["path"]) not in self._hashes
        ]
        if not pending:
            return None
        thread = threading.Thread(
            target=self._hash_worker, args=(pending,), daemon=True
        )
        self._hash_thread = thread
        thread.start()
        return thread

    def _hash_worker(self, pending):
        for item in pending:
            try:
                value = digest(item)
            except OSError:
                value = ""
            self._post_hash(item, value)

    def _post_hash(self, item, value):
        # The digest lands in the map first: a plain dict write is safe from this
        # thread and the next repaint picks the value up even if Tk cannot be
        # reached right now.
        self._hashes[item] = value

        def apply():
            tree = self._preview_tree
            if tree is None:
                return
            try:
                index = next(
                    (str(record["index"]) for record in self.entries()
                     if str(record["path"]) == item), None
                )
                if index is not None:
                    tree.set(index, "sha", value[:16] if value else "unreadable")
            except tk.TclError:
                pass
        try:
            self.root.after(0, apply)
        except (tk.TclError, RuntimeError):
            # No main loop to schedule on: the digest stays in the map for the
            # next repaint. Tk is never touched from this thread.
            pass

    # --------------------------------------------------------------- clipboard
    def selection_text(self):
        return "\n".join(str(path) for path in self.selected_files)

    def copy_list(self):
        if not self.selected_files:
            self.status.set("Nothing to copy.")
            return ""
        text = self.selection_text()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except tk.TclError:
            self.status.set("Clipboard unavailable.")
            return text
        self.status.set(f"Copied {len(self.selected_files)} path(s) to the clipboard.")
        return text

    def save_list(self):
        if not self.selected_files:
            self.status.set("Nothing to save.")
            return None
        target = filedialog.asksaveasfilename(
            parent=self.frame, title="Save the selected file list",
            defaultextension=".txt", initialfile="selection.txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if not target:
            return None
        body = self.selection_text()
        try:
            Path(target).write_text(body + "\n", encoding="utf-8")
        except OSError as exc:
            self.status.set(f"Cannot write the list: {exc}")
            return None
        self.status.set(f"Saved {len(self.selected_files)} path(s) to {target}.")
        return target

    # ---------------------------------------------------------------- checking
    def check_selection(self, notify=False):
        """Fail closed on anything the pipeline would refuse; returns True when ready."""
        blockers = []
        warnings = []
        if not self.selected_files:
            blockers.append('Add at least one file with "Add files...".')
        absent = file_selection.missing(self.selected_files)
        if absent:
            blockers.append(
                "Selected file(s) no longer exist or are not readable: "
                + ", ".join(str(item) for item in absent[:5])
            )
        anchor = self.anchor()
        if anchor is None:
            typed = self.evidence_root.get().strip()
            blockers.append(
                "That evidence root folder does not exist." if typed
                else "Choose the folder that contains the files (evidence root)."
            )
        elif self.selected_files:
            outside = [path for path in self.selected_files if not _contains(anchor, path)]
            if outside:
                warnings.append(
                    f"{len(outside)} file(s) live outside the evidence root, so their paths stay "
                    'absolute. Press "Derive from files" for clean relative paths.'
                )
        self.problems = blockers
        self.warnings = warnings
        if blockers:
            self.status.set(blockers[0])
            if notify:
                messagebox.showwarning(
                    "ChronoSeal Report from Files", "\n\n".join(blockers), parent=self.frame
                )
            return False
        if warnings:
            self.status.set(warnings[0])
        else:
            self.status.set(
                f"{len(self.selected_files)} file(s) ready - the list is the evidence set."
            )
        return True

    # --------------------------------------------------------------- handover
    def hand_over(self):
        """Publish the selection to the main window without starting anything."""
        if not self.selected_files:
            self.status.set("Nothing to hand over.")
            return False
        anchor = self.anchor()
        if anchor is None:
            self.status.set("Choose the evidence root folder first.")
            return False
        self.root.target.set(str(anchor))
        self.root.file_filters = []
        self.root.file_selection = [str(path) for path in self.selected_files]
        sync = getattr(self.root, "_sync_input_mode", None)
        if callable(sync):
            try:
                sync()
            except (AttributeError, tk.TclError):
                pass
        recursive = getattr(self.root, "rec", None)
        if recursive is not None:
            try:
                recursive.set(False)
            except tk.TclError:
                pass
        refresh = getattr(self.root, "_refresh_filter_indicator", None)
        if callable(refresh):
            try:
                refresh()
            except tk.TclError:
                pass
        self.status.set(
            f"{len(self.selected_files)} file(s) handed over - press Generate on Report & TSA, "
            "or use Create combo report."
        )
        return True

    def create_report(self):
        if not self.check_selection(notify=True):
            return False
        if not getattr(self.root, "startup_ready", False):
            self.hand_over()
            messagebox.showinfo(
                "ChronoSeal Report from Files",
                "The selection was handed over to Report & TSA.\n\n"
                "Startup qualification has not passed yet, so the report was not started. "
                "Open Report & TSA and press Generate once qualification passes.",
                parent=self.frame,
            )
            return False
        if not self.hand_over():
            return False
        select = getattr(self.root, "_select_page", None)
        if callable(select):
            try:
                select("run_tab")
            except (AttributeError, tk.TclError):
                pass
        start = getattr(self.root, "start", None)
        if not callable(start):
            self.status.set("This window cannot start a report.")
            return False
        try:
            start()
        except tk.TclError as exc:
            self.status.set(f"Could not start the report: {exc}")
            return False
        # The run arguments hold their own copy, so a finished hand-over must not
        # leave a stale selection behind for the next folder report.
        self.root.file_selection = []
        refresh = getattr(self.root, "_refresh_filter_indicator", None)
        if callable(refresh):
            try:
                refresh()
            except tk.TclError:
                pass
        self.status.set("Combo report started - follow the log on Report & TSA.")
        return True