"""Hash Report Generator dynamic loader.

Public API:
    from loader import load_helpers, load_rfc3161

    helpers = load_helpers({"logger": my_logger})
    helpers["registry"].run("beforeGenerate", {"reportId": "RPT-..."})
"""
from __future__ import annotations

import importlib

from ._loader_core import load_package
from ._registry import Registry


def _load_subpackage(name: str, context: dict | None) -> dict:
    pkg = importlib.import_module(f"{__name__}.{name}")
    return load_package(pkg, name, context)


def load_helpers(context: dict | None = None) -> dict:
    return _load_subpackage("helper", context)


def load_rfc3161(context: dict | None = None) -> dict:
    return _load_subpackage("rfc3161", context)


__all__ = ["Registry", "load_helpers", "load_rfc3161"]