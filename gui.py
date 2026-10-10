"""GitSU portable launcher: run with Python 3 on Windows."""
from __future__ import annotations
import hashlib
import locale
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
APP = DATA / "app"
TOOLS = DATA / "tools"
LOG = DATA / "logs" / "launcher.log"
NODE_VERSION = "v22.12.0"
LAUNCH_LANG = "de" if (locale.getlocale()[0] or "").lower().startswith("de") else "bg"
def lt(bg, de):
    return de if LAUNCH_LANG == "de" else bg


def record(message):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def portable_node():
    node = TOOLS / "node" / "node.exe"
    npm = TOOLS / "node" / "npm.cmd"
    if node.is_file() and npm.is_file():
        return node, npm
    # Prefer an already available local/system Node.js installation.
    system_node, system_npm = shutil.which("node"), shutil.which("npm.cmd") or shutil.which("npm")
    if system_node and system_npm:
        return Path(system_node), Path(system_npm)
    if sys.platform != "win32":
        raise RuntimeError("Automatic Node.js bootstrap is supported on Windows only")
    import platform
    arch = "win-x64" if platform.machine().lower() in ("amd64", "x86_64") else "win-arm64" if platform.machine().lower() in ("arm64", "aarch64") else None
    if arch is None:
        raise RuntimeError("Unsupported Windows architecture")
    filename = f"node-{NODE_VERSION}-{arch}.zip"
    base = f"https://nodejs.org/dist/{NODE_VERSION}/"
    cache = TOOLS / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    sums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=45).read().decode("ascii")
    expected = next((line.split()[0] for line in sums.splitlines() if line.split()[-1] == filename), None)
    if not expected:
        raise RuntimeError("Node.js archive checksum not listed by publisher")
    archive = cache / filename
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        record("Downloading official Node.js archive")
        urllib.request.urlretrieve(base + filename, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Node.js SHA-256 verification failed")
    destination = TOOLS / "node"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        prefix = filename[:-4] + "/"
        for info in z.infolist():
            if not info.filename.startswith(prefix):
                raise RuntimeError("Unexpected Node.js archive path")
            relative = Path(info.filename[len(prefix):])
            if not relative.parts or info.is_dir():
                continue
            if ".." in relative.parts or relative.is_absolute():
                raise RuntimeError("Unsafe Node.js archive path")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
    if not node.exists() or not npm.exists():
        raise RuntimeError("Node.js extraction incomplete")
    return node, npm


def run_process(args, *, cwd=None, env=None):
    record("Running: " + str(args[0]))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with subprocess.Popen([str(x) for x in args], cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors="replace", creationflags=flags) as p:
        for line in p.stdout:
            record(line.rstrip())
        code = p.wait()
    if code:
        raise RuntimeError(f"Command failed (exit {code}); see {LOG}")


def _pid_alive(text):
    try:
        import ctypes
        pid = int(text)
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def acquire_lock():
    # One launcher at a time: parallel npm installs on the same folder corrupt node_modules.
    lock = DATA / "launcher.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        if lock.exists() and not _pid_alive(lock.read_text().strip()):
            lock.unlink()
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        raise RuntimeError(lt("Друг стартер вече подготвя GitSU. Изчакайте.", "Ein anderer Start läuft bereits."))
    return lock


def prebuilt_exe():
    # Packaged app (release/GitSU-win-x64-*.zip) extracted once to a LOCAL disk: no npm, no SMB-hosted Electron.
    zips = sorted((ROOT / "release").glob("GitSU-win-x64-*.zip"), key=lambda z: z.stat().st_mtime, reverse=True)
    if not zips:
        return None
    z = zips[0]
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "GitSU"
    target = base / f"{z.stem}-{z.stat().st_size}"
    exe = target / "GitSU.exe"
    if exe.is_file():
        return exe
    record("Extracting " + z.name + " to " + str(target))
    tmp = base / (target.name + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():
            if not (tmp / m.filename).resolve().is_relative_to(tmp.resolve()):
                raise RuntimeError("Unsafe archive path")
        zf.extractall(tmp)
    tmp.rename(target)
    return exe


def launch():
    if sys.platform != "win32":
        raise RuntimeError("GitSU desktop launcher requires Windows")
    exe = prebuilt_exe()
    if exe:
        env = os.environ.copy()
        env.pop("ELECTRON_RUN_AS_NODE", None)
        env["GITSU_PORTABLE_DATA"] = str(DATA / "user-data")
        (DATA / "user-data").mkdir(parents=True, exist_ok=True)
        subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env, close_fds=True)
        return lt("GitSU е стартиран", "GitSU wurde gestartet")
    # Ready-to-use bundled engine takes precedence. No install and no npm needed.
    engine = DATA / "runtime" / "GitSU-Engine.exe"
    if engine.is_file():
        subprocess.Popen([str(engine)], cwd=DATA / "runtime", close_fds=True)
        return lt("GitSU е стартиран", "GitSU wurde gestartet")
    node, npm = portable_node()
    electron = APP / "node_modules" / "electron" / "dist" / "electron.exe"
    if not electron.is_file():
        env = os.environ.copy()
        env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
        env["ELECTRON_CACHE"] = str(DATA / "cache" / "electron")
        env["npm_config_cache"] = str(DATA / "cache" / "npm")
        env["ELECTRON_RUN_AS_NODE"] = "0"
        run_process([npm, "install", "--no-audit", "--no-fund", "--ignore-scripts=false"], cwd=APP, env=env)
    if not electron.is_file():
        raise RuntimeError("Electron executable is missing after dependency installation")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    env["GITSU_PORTABLE_DATA"] = str(DATA / "user-data")
    env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
    (DATA / "user-data").mkdir(parents=True, exist_ok=True)
    subprocess.Popen([str(electron), str(APP)], cwd=APP, env=env, close_fds=True)
    return lt("GitSU е стартиран", "GitSU wurde gestartet")


def main():
    try:
        from tkinter import Tk, Label, Button, Text, END, messagebox
        from tkinter import ttk
    except ImportError:
        print("Python tkinter is required")
        raise
    root = Tk()
    root.title("GitSU SUPERUSER · Portable")
    root.geometry("660x300")
    root.configure(bg="#0b1426")
    Label(root, text="GitSU  SUPERUSER", font=("Segoe UI", 22, "bold"), bg="#0b1426", fg="#f2f6ff").pack(pady=(25, 4))
    Label(root, text="ENTERPRISE PRO  ·  PasevSU-DEV  ·  Portable", font=("Segoe UI", 10), bg="#0b1426", fg="#4fc3ff").pack()
    status = Label(root, text=lt("Подготовка на GitSU…", "GitSU wird vorbereitet…"), wraplength=590, bg="#0b1426", fg="#d3e3f7", font=("Segoe UI", 10))
    status.pack(pady=(35, 15))
    progress = ttk.Progressbar(root, mode="indeterminate", length=490)
    progress.pack()
    progress.start(12)
    def worker():
        lock = None
        try:
            lock = acquire_lock()
            result = launch()
            root.after(0, lambda: (status.config(text=result), progress.stop(), root.after(1100, root.destroy)))
        except Exception as exc:
            record("ERROR: " + repr(exc))
            msg = str(exc)
            root.after(0, lambda: (progress.stop(), status.config(text=lt("Грешка при стартиране — ", "Start fehlgeschlagen — ") + msg), messagebox.showerror(lt("Стартиране на GitSU", "GitSU-Start"), msg + "\n\nLog: " + str(LOG))))
        finally:
            if lock:
                lock.unlink(missing_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    main()
