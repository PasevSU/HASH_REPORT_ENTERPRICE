"""ChronoSeal canonical entrypoint: always open the single unified workspace."""
from pathlib import Path
import importlib.machinery
import importlib.util

base = Path(__file__).resolve().parent
source = base / "ChronoSeal_GUI.pyw"
loader = importlib.machinery.SourceFileLoader("chronoseal_unified_gui", str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

App = module.ChronoSealDesktop
messagebox = module.messagebox

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
