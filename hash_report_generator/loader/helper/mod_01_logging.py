"""Structured logging helper."""
from __future__ import annotations


def register(api):
    logger = api.get("logger")
    tag = "[helper:logging]"

    def _log(msg, extra=None):
        if logger:
            logger.info(f"{tag} {msg} {extra or ''}".rstrip())

    def before_timestamp(ctx, _registry):
        _log("beforeTimestamp", {
            "reportId": ctx.get("reportId"),
            "marker": ctx.get("marker"),
        })

    def after_validation(ctx, _registry):
        _log("afterValidation", {"ok": ctx.get("validationOk")})

    return {
        "id": "logging",
        "version": "1.0.0",
        "priority": 10,
        "description": "Structured logging helper",
        "hooks": {
            "beforeTimestamp": before_timestamp,
            "afterValidation": after_validation,
        },
    }