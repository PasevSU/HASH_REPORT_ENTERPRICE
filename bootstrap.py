"""Standard-library-only, user-approved dependency bootstrap for ChronoSeal Qt."""
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import venv

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.chronoseal-venv'
LOG = ROOT / 'bootstrap.log'
REQ = ROOT / 'requirements.txt'


def python_in_venv():
    return VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def check_environment():
    result = []
    for label, path in [('Original GUI', ROOT / 'ChronoSeal_GUI.pyw'),
                        ('Legacy engine', ROOT / 'ChronoSeal_Original_Legacy.py'),
                        ('Automation', ROOT / 'automation' / 'Start_Automation.py')]:
        result.append((label, path.is_file(), str(path.relative_to(ROOT))))
    try:
        version = metadata.version('PySide6')
        from packaging.version import Version
        ok = Version('6.7') <= Version(version) < Version('7')
    except ImportError:
        # packaging is optional: avoid depending on it for bootstrapping
        try:
            version = metadata.version('PySide6')
            major, minor = (int(x) for x in version.split('.')[:2])
            ok = major == 6 and minor >= 7
        except (metadata.PackageNotFoundError, ValueError):
            version, ok = 'missing', False
    except (metadata.PackageNotFoundError, ValueError):
        version, ok = 'missing', False
    result.insert(0, ('PySide6', ok, version))
    return result


def run_qt():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    from desktop import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('ChronoSeal Enterprise')
    app.setFont(QFont('Segoe UI', 10))
    window = MainWindow(ROOT)
    window.show()
    return app.exec()


class Bootstrap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ChronoSeal · Проверка на средата')
        self.geometry('740x470')
        self.minsize(620, 400)
        self.configure(bg='#101c2e')
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#101c2e')
        self.style.configure('TLabel', background='#101c2e', foreground='#e8f1ff', font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10), padding=8)
        self.style.configure('TProgressbar', troughcolor='#1a304a', background='#2378ea')
        panel = ttk.Frame(self, padding=22); panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='ChronoSeal · Dependency Manager', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Локална проверка. Нищо не се инсталира без потвърждение.').pack(anchor='w', pady=(4, 14))
        self.table = ttk.Treeview(panel, columns=('state', 'detail'), show='headings', height=7)
        for col, width in [('state', 120), ('detail', 440)]:
            self.table.heading(col, text='Статус' if col == 'state' else 'Компонент / детайли')
            self.table.column(col, width=width)
        self.table.pack(fill='both', expand=True)
        self.progress = ttk.Progressbar(panel, mode='indeterminate'); self.progress.pack(fill='x', pady=(12, 4))
        self.message = tk.StringVar(value='')
        ttk.Label(panel, textvariable=self.message, wraplength=650).pack(anchor='w')
        actions = ttk.Frame(panel); actions.pack(fill='x', pady=(12, 0))
        self.install = ttk.Button(actions, text='Инсталирай липсващите GUI пакети', command=self.install_missing)
        self.install.pack(side='left')
        self.launch = ttk.Button(actions, text='Стартирай ChronoSeal', command=self.launch_qt)
        self.launch.pack(side='left', padx=8)
        ttk.Button(actions, text='Повторна проверка', command=self.refresh).pack(side='right')
        self.refresh()

    def refresh(self):
        for item in self.table.get_children(): self.table.delete(item)
        states = check_environment()
        for name, ok, detail in states:
            self.table.insert('', 'end', values=('OK' if ok else 'ЛИПСВА', f'{name} — {detail}'))
        self.gui_ready = states[0][1]
        self.install.configure(state='disabled' if self.gui_ready else 'normal')
        self.launch.configure(state='normal' if self.gui_ready else 'disabled')
        missing = [name for name, ok, _ in states[1:] if not ok]
        self.message.set('Липсващи оригинални компоненти: ' + ', '.join(missing) + '. GUI може да се отвори, но оригиналните функции няма да са налични.' if missing else 'Оригиналните входни файлове са налични. Това не доказва работоспособността на всички зависимости на engine.')

    def install_missing(self):
        if not messagebox.askyesno('Инсталация', 'Да създам изолирана .chronoseal-venv среда и да инсталирам PySide6? Не променям системния Python. Необходим е достъп до PyPI.'):
            return
        self.install.configure(state='disabled'); self.launch.configure(state='disabled')
        self.progress.start(12)
        self.message.set('Инсталацията се изпълнява...')
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            if not python_in_venv().is_file():
                venv.EnvBuilder(with_pip=True).create(str(VENV))
            commands = [[str(python_in_venv()), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(REQ)],
                        [str(python_in_venv()), '-m', 'pip', 'check']]
            with LOG.open('a', encoding='utf-8') as log:
                for command in commands:
                    completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=900, check=False)
                    if completed.returncode:
                        raise RuntimeError(f'Команда завърши с код {completed.returncode}: {command[3:]}')
            self.after(0, self.install_success)
        except Exception as exc:
            self.after(0, lambda err=str(exc): self.install_failure(err))

    def install_success(self):
        self.progress.stop()
        self.message.set('Пакетите са инсталирани в изолирана среда. Стартирай приложението.')
        self.install.configure(state='normal')
        self.launch.configure(state='normal')

    def install_failure(self, err):
        self.progress.stop(); self.install.configure(state='normal')
        self.message.set(f'Инсталацията не успя: {err}. Виж bootstrap.log')
        messagebox.showerror('Инсталацията е прекъсната', f'{err}\nПодробности: {LOG}')

    def launch_qt(self):
        exe = python_in_venv() if python_in_venv().is_file() else Path(sys.executable)
        if not exe.is_file():
            messagebox.showerror('Python', f'Липсва интерпретатор: {exe}'); return
        subprocess.Popen([str(exe), str(ROOT / 'start-new.pyw'), '--qt'], cwd=ROOT)
        self.destroy()


def main():
    if '--qt' in sys.argv:
        try:
            sys.exit(run_qt())
        except Exception as exc:
            import traceback
            LOG.write_text(traceback.format_exc(), encoding='utf-8')
            from chronoseal.tk_support import create_root
            root = create_root(); root.withdraw()
            messagebox.showerror('ChronoSeal', f'Не може да стартира Qt: {exc}\n{LOG}')
            root.destroy()
            sys.exit(1)
    states = check_environment()
    if states[0][1]:
        sys.exit(run_qt())
    if python_in_venv().is_file():
        subprocess.Popen([str(python_in_venv()), str(ROOT / 'start-new.pyw'), '--qt'], cwd=ROOT)
        return
    Bootstrap().mainloop()
