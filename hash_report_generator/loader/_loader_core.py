"""Dynamic module discovery and loading."""
from __future__ import annotations

import importlib
import pkgutil
import sys

from ._registry import Registry

_IGNORE_PREFIX = "_"
_IGNORE_SUFFIXES = ("_test", "_spec")


def discover_modules(package) -> list:
    """Return importable module names inside a package directory."""
    names = []
    for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
        if is_pkg:
            continue
        if name.startswith(_IGNORE_PREFIX):
            continue
        if any(name.endswith(s) for s in _IGNORE_SUFFIXES):
            continue
        names.append(name)
    return sorted(names)


def load_package(package, name: str, context: dict | None = None) -> dict:
    registry = Registry(name)
    context = context or {}
    loaded, skipped = [], []

    api = {
        "Registry": Registry,
        "registry": registry,
        "context": context,
        "logger": context.get("logger"),
    }

    for mod_name in discover_modules(package):
        try:
            full = f"{package.__name__}.{mod_name}"
            if full in sys.modules:
                del sys.modules[full]
            mod = importlib.import_module(full)

            register = getattr(mod, "register", None)
            if not callable(register):
                skipped.append({"module": mod_name, "reason": "no register()"})
                continue

            info = register(api)
            if not info or not info.get("id"):
                skipped.append({"module": mod_name, "reason": "register() returned no id"})
                continue

            registry.register(info)
            loaded.append({
                "module": mod_name,
                "id": info["id"],
                "version": info.get("version", "0.0.0"),
                "priority": int(info.get("priority", 100)),
            })
        except Exception as exc:
            registry.errors.append({"module": mod_name, "error": str(exc)})
            skipped.append({"module": mod_name, "reason": str(exc)})

    return {
        "registry": registry,
        "loaded": loaded,
        "skipped": skipped,
        "files": discover_modules(package),
        "summary": registry.summary(),
    }