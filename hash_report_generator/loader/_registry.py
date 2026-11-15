"""Module registry with hook dispatch."""
from __future__ import annotations


class Registry:
    def __init__(self, name: str):
        self.name = name
        self.modules: dict = {}
        self.hooks: dict = {}
        self.errors: list = []

    def register(self, info: dict) -> None:
        module_id = info.get("id")
        if not module_id:
            raise ValueError("Module must declare an 'id'")
        if module_id in self.modules:
            raise ValueError(f"Duplicate module id: {module_id}")

        self.modules[module_id] = info

        for hook_name, fn in (info.get("hooks") or {}).items():
            if not callable(fn):
                continue
            self.hooks.setdefault(hook_name, []).append({
                "id": module_id,
                "priority": int(info.get("priority", 100)),
                "fn": fn,
            })

    def get(self, module_id: str):
        return self.modules.get(module_id)

    def has(self, module_id: str) -> bool:
        return module_id in self.modules

    def list(self) -> list:
        return sorted(self.modules.keys())

    def hook_names(self) -> list:
        return sorted(self.hooks.keys())

    def run(self, hook_name: str, ctx: dict | None = None) -> dict:
        ctx = ctx or {}
        handlers = sorted(
            self.hooks.get(hook_name, []),
            key=lambda h: (h["priority"], h["id"]),
        )
        for h in handlers:
            try:
                h["fn"](ctx, self)
            except Exception as exc:
                self.errors.append({
                    "hook": hook_name,
                    "module": h["id"],
                    "error": str(exc),
                })
                if ctx.get("strict"):
                    raise
        return ctx

    def summary(self) -> dict:
        return {
            "name": self.name,
            "modules": self.list(),
            "hooks": self.hook_names(),
            "errors": len(self.errors),
        }