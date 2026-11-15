#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple peripheral GUI for Hash Report Generators v2.34.

This file intentionally does not modify the report/crypto/database modules.  It
only launches their existing command-line entry points and provides a compact
Windows-friendly front end.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_VERSION = "2.34"
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))
from chronoseal import i18n
i18n.install()

ACTIONS = {
    "combined": {
        "title": "Combined report",
        "script": "hash_report_combined.py",
        "needs": "path",
        "hint": "Изберете evidence папка или EML файл.",
    },
    "single": {
        "title": "Single report",
        "script": "hash_report_single.py",
        "needs": "file",
        "hint": "Изберете файл за индивидуален HASHREPORT.",
    },
    "extract": {
        "title": "Extract RFC 3161",
        "script": "extract_rfc3161.py",
        "needs": "pdf",
        "hint": "Изберете HASHREPORT.pdf. Артефактите се извличат в отделна папка.",
    },
    "verify_rfc": {
        "title": "Verify RFC 3161",
        "script": "verify_rfc3161_evidence.py",
        "needs": "pdf",
        "hint": "Изберете HASHREPORT.pdf за offline RFC 3161 проверка.",
    },
    "verify_db": {
        "title": "Verify SQLite",
        "script": "evidence_database.py",
        "needs": "database",
        "hint": "Изберете hash_report_evidence.sqlite3.",
    },
    "tsa": {
        "title": "TSA diagnostic",
        "script": "tsa_diagnostic.py",
        "needs": "none",
        "hint": "Проверява OpenSSL, TSA endpoints и RFC 3161 failover.",
    },
}


def _creation_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _open_path(path: Path) -> None:
    path = Path(path)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _show_in_folder(path: Path) -> None:
    path = Path(path)
    if path.is_dir():
        _open_path(path)
        return
    if os.name == "nt":
        subprocess.Popen(["explorer.exe", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


class ResultDialog(tk.Toplevel):
    """Three-choice completion dialog: open / show in folder / OK."""

    def __init__(self, parent: tk.Misc, title: str, message: str,
                 target: Path | None = None) -> None:
        super().__init__(parent)
        self.target = Path(target) if target else None
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=18)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text=message, justify="left", wraplength=560).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))

        open_btn = ttk.Button(frame, text="Отвори файла", command=self._open)
        show_btn = ttk.Button(frame, text="Покажи в папката", command=self._show)
        ok_btn = ttk.Button(frame, text="OK", command=self.destroy)
        open_btn.grid(row=1, column=0, padx=(0, 8))
        show_btn.grid(row=1, column=1, padx=8)
        ok_btn.grid(row=1, column=2, padx=(8, 0))

        if not self.target or not self.target.exists():
            open_btn.state(["disabled"])
            show_btn.state(["disabled"])

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.destroy())
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")
        ok_btn.focus_set()

    def _open(self) -> None:
        try:
            if self.target:
                _open_path(self.target)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self)

    def _show(self) -> None:
        try:
            if self.target:
                _show_in_folder(self.target)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Грешка", str(exc), parent=self)


class HashReportGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"Hash Report Generator v{APP_VERSION} – GUI")
        self.geometry("920x650")
        self.minsize(780, 560)

        self.path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готов")
        self.hint_var = tk.StringVar(value="Изберете функция и входен файл/папка.")
        self._messages: queue.Queue[tuple] = queue.Queue()
        self._running = False
        self._action_buttons: list[ttk.Button] = []

        self._build_ui()
        self.after(100, self._drain_messages)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text=f"HASH REPORT GENERATOR v{APP_VERSION}",
                          font=("Segoe UI", 15, "bold"))
        title.pack(anchor="w")
        i18n.add_language_selector(outer, self, side="top", anchor="e")
        ttk.Label(outer, text="GUI launcher – основните модули остават непроменени").pack(
            anchor="w", pady=(2, 12))

        source = ttk.LabelFrame(outer, text="Вход", padding=10)
        source.pack(fill="x")
        source.columnconfigure(0, weight=1)
        ttk.Entry(source, textvariable=self.path_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(source, text="Файл…", command=self._browse_file).grid(row=0, column=1, padx=4)
        ttk.Button(source, text="Папка…", command=self._browse_folder).grid(row=0, column=2, padx=(4, 0))

        actions = ttk.LabelFrame(outer, text="Функции", padding=10)
        actions.pack(fill="x", pady=(12, 0))
        for col in range(3):
            actions.columnconfigure(col, weight=1)

        specs = [
            ("combined", "Combined report"),
            ("single", "Single report"),
            ("extract", "Extract RFC 3161"),
            ("verify_rfc", "Verify RFC 3161"),
            ("verify_db", "Verify SQLite"),
            ("tsa", "TSA diagnostic"),
        ]
        for idx, (key, label) in enumerate(specs):
            btn = ttk.Button(actions, text=label, command=lambda k=key: self._start_action(k))
            btn.grid(row=idx // 3, column=idx % 3, sticky="ew", padx=5, pady=5, ipady=5)
            self._action_buttons.append(btn)

        ttk.Label(outer, textvariable=self.hint_var, foreground="#555555").pack(
            fill="x", pady=(8, 4))

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(4, 8))
        ttk.Label(status, textvariable=self.status_var).pack(side="left")
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=220)
        self.progress.pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="Изход / Log", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = ScrolledText(log_frame, wrap="word", height=18, font=("Consolas", 9))
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Изчисти log", command=self._clear_log).pack(side="left")
        ttk.Button(bottom, text="Затвори", command=self.destroy).pack(side="right")

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(title="Изберете файл")
        if path:
            self.path_var.set(path)

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(title="Изберете папка")
        if path:
            self.path_var.set(path)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        self._running = running
        for btn in self._action_buttons:
            if running:
                btn.state(["disabled"])
            else:
                btn.state(["!disabled"])
        if running:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _validate_input(self, key: str) -> Path | None:
        need = ACTIONS[key]["needs"]
        if need == "none":
            return None
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Липсва вход", "Изберете файл или папка.", parent=self)
            return None
        path = Path(raw).expanduser()
        if not path.exists():
            messagebox.showerror("Грешка", f"Пътят не съществува:\n{path}", parent=self)
            return None
        if need in {"file", "pdf", "database"} and not path.is_file():
            messagebox.showerror("Грешка", "За тази функция трябва да изберете файл.", parent=self)
            return None
        if need == "pdf" and path.suffix.lower() != ".pdf":
            messagebox.showerror("Грешка", "Изберете PDF файл.", parent=self)
            return None
        if need == "database" and path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            if not messagebox.askyesno(
                    "SQLite?", "Файлът няма стандартно SQLite разширение. Да продължа ли?", parent=self):
                return None
        if key == "combined" and path.is_file() and path.suffix.lower() != ".eml":
            messagebox.showerror(
                "Combined report",
                "Combined mode приема evidence папка или EML файл.\nЗа произволен единичен файл използвайте Single report.",
                parent=self)
            return None
        return path.resolve()

    def _start_action(self, key: str) -> None:
        if self._running:
            return
        selected = self._validate_input(key)
        if ACTIONS[key]["needs"] != "none" and selected is None:
            return

        self.hint_var.set(ACTIONS[key]["hint"])
        self.status_var.set(f"Изпълнява се: {ACTIONS[key]['title']} …")
        self._append_log("\n" + "=" * 78 + "\n")
        self._append_log(f"{ACTIONS[key]['title']}\n")
        if selected:
            self._append_log(f"Input: {selected}\n")
        self._append_log("=" * 78 + "\n")
        self._set_running(True)

        thread = threading.Thread(target=self._worker, args=(key, selected), daemon=True)
        thread.start()

    def _worker(self, key: str, selected: Path | None) -> None:
        started = time.time()
        script = BASE_DIR / ACTIONS[key]["script"]
        if not script.is_file():
            self._messages.put(("done", key, 2, selected, None,
                                f"Липсва модул: {script.name}"))
            return

        cmd = [sys.executable, str(script)]
        if selected is not None:
            cmd.append(str(selected))

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                creationflags=_creation_flags(),
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self._messages.put(("log", line))
            rc = proc.wait()
            target = self._result_target(key, selected, started, rc)
            # The combined CLI historically returns 0 even when no report was
            # produced (for example an EML without enough artifacts).  The GUI
            # treats "no new PDF" as an unsuccessful generation instead of
            # presenting the source file as a result.
            if rc == 0 and key in {"combined", "single"} and target is None:
                rc = 3
                self._messages.put(("log", "\nGUI: no new HASHREPORT.pdf was created.\n"))
            self._messages.put(("done", key, rc, selected, target, None))
        except Exception as exc:
            self._messages.put(("done", key, 2, selected, None, str(exc)))

    @staticmethod
    def _newest_report(folder: Path, started: float) -> Path | None:
        candidates = []
        try:
            for p in folder.glob("*-HASHREPORT.pdf"):
                if "ERLAEUTERUNG" in p.name.upper():
                    continue
                try:
                    if p.stat().st_mtime >= started - 2:
                        candidates.append(p)
                except OSError:
                    pass
        except OSError:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

    def _result_target(self, key: str, selected: Path | None,
                       started: float, rc: int) -> Path | None:
        if rc != 0:
            return selected
        if key in {"combined", "single"} and selected:
            folder = selected if selected.is_dir() else selected.parent
            return self._newest_report(folder, started)
        if key == "extract" and selected:
            out_dir = selected.with_name(selected.stem + "_RFC3161")
            return out_dir if out_dir.exists() else selected
        if key in {"verify_rfc", "verify_db"}:
            return selected
        return None

    def _drain_messages(self) -> None:
        try:
            while True:
                msg = self._messages.get_nowait()
                if not msg:
                    continue
                if msg[0] == "log":
                    self._append_log(msg[1])
                elif msg[0] == "done":
                    _, key, rc, selected, target, error = msg
                    self._finish_action(key, rc, selected, target, error)
        except queue.Empty:
            pass
        self.after(100, self._drain_messages)

    def _finish_action(self, key: str, rc: int, selected: Path | None,
                       target: Path | None, error: str | None) -> None:
        self._set_running(False)
        title = ACTIONS[key]["title"]
        if error:
            self.status_var.set(f"Грешка: {title}")
            self._append_log(f"\nERROR: {error}\n")
            messagebox.showerror("Грешка", error, parent=self)
            return
        if rc != 0:
            self.status_var.set(f"Неуспешно: {title} (код {rc})")
            ResultDialog(
                self,
                "Проверката не завърши успешно",
                f"{title} приключи с код {rc}.\nВижте Log за подробности.",
                target or selected,
            )
            return

        self.status_var.set(f"Готово: {title}")
        if target:
            message = f"{title} приключи успешно.\n\nРезултат:\n{target}"
        else:
            message = f"{title} приключи успешно."
        ResultDialog(self, "Готово", message, target)


if __name__ == "__main__":
    app = HashReportGUI()
    app.mainloop()
