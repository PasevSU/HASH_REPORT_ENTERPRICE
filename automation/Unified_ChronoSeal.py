"""One Tk root, one Notebook: original UI plus standalone automation tab.
Original ChronoSeal source files are never modified.
"""
from pathlib import Path
import sys
import importlib.machinery
import importlib.util
from tkinter import ttk
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(HERE))
from Start_Automation import App as AutomationPanel
source = BASE / "ChronoSeal_OneButton.py"
loader = importlib.machinery.SourceFileLoader("chronoseal_original_ui", str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

class UnifiedApp(module.App):
    def _ui(self):
        super()._ui()
        tab = ttk.Frame(self.nb, padding=4)
        self.nb.add(tab, text="Automatic Reports")
        self.automation_panel = AutomationPanel(self, parent=tab)

if __name__ == "__main__":
    app = UnifiedApp()
    app.mainloop()
