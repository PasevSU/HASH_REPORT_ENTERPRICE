"""Strict access to migrated presentation rules; no local defaults."""
from functools import lru_cache
from .style_loader import load_styles

@lru_cache(maxsize=1)
def _values():
    return load_styles()["MIGRATED_VISUAL_LITERALS"]

def visual(key):
    return _values()[key]

@lru_cache(maxsize=1)
def _semantic_values():
    return load_styles()["CENTRAL_LAYOUT"]

def layout_rule(*path):
    node = _semantic_values()
    for key in path:
        node = node[key]
    return node
