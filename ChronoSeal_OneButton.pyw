"""ChronoSeal quick start (.pyw): open the single unified workspace, no console.

This is a *launcher only*. It adds no logic to the application and changes no
existing file: it loads ``ChronoSeal_GUI.pyw`` the same way
``Start_ChronoSeal.bat`` already does, then opens the same
``ChronoSealDesktop`` window.

Why a ``.pyw`` file:

* double-click opens the workspace straight away - Windows runs ``.pyw`` with
  ``pythonw.exe``, so no console window flashes and none stays open;
* because there is no console, an import or start-up failure would be
  completely invisible, so every exception is caught and shown in a dialog
  instead of dying silently in a hidden process.

Use ``Start_ChronoSeal.bat`` when you want a terminal, and this file when you
want the fastest possible silent start from Explorer, the Start menu or a
shortcut.
"""
from pathlib import Path
import importlib.machinery
import importlib.util
import os
import sys
import traceback

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "ChronoSeal_GUI.pyw"

# ``Start_ChronoSeal.bat`` already does ``cd /d "%~dp0"``. Doing the same here
# keeps relative settings (config/, logs/, ChronoSeal_Archive/) pointing at the
# project folder even when the file is opened by double-click from elsewhere.
try:
    os.chdir(BASE)
except OSError:
    pass

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "automation"))


def _fatal(title, message):
    """Report a start-up failure without a console (the .pyw failure mode)."""
    text = f"{message}\n\nProject folder:\n{BASE}"
    try:
        from tkinter import messagebox

        messagebox.showerror(title, text)
    except Exception:
        # Tk could not even start: last resort is the Windows message box.
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
        except Exception:
            pass


def _load_gui():
    """Load ``ChronoSeal_GUI.pyw`` as a module, like the sibling entry points."""
    if not SOURCE.is_file():
        raise FileNotFoundError(f"ChronoSeal_GUI.pyw was not found in {BASE}")
    loader = importlib.machinery.SourceFileLoader("chronoseal_unified_gui", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main():
    try:
        module = _load_gui()
    except Exception as exc:
        _fatal("ChronoSeal - start-up failed", f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc

    try:
        app = module.ChronoSealDesktop()
        # Always on top once, so a double-click start cannot hide behind Explorer.
        try:
            app.lift()
            app.attributes("-topmost", True)
            app.after(300, lambda: app.attributes("-topmost", False))
        except Exception:
            pass
        app.mainloop()
    except Exception as exc:
        _fatal(
            "ChronoSeal - the workspace stopped",
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
