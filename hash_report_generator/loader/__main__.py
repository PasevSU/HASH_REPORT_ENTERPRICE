"""CLI smoke test:  python -m loader"""
from __future__ import annotations

import json
import logging

from . import load_helpers, load_rfc3161


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("loader-smoke")

    for name, fn in (("helper", load_helpers), ("rfc3161", load_rfc3161)):
        result = fn({"logger": logger})
        print(f"\n=== {name} ===")
        print("summary:", json.dumps(result["summary"], ensure_ascii=False))
        print("loaded :", json.dumps(result["loaded"], ensure_ascii=False, indent=2))
        if result["skipped"]:
            print("skipped:", json.dumps(result["skipped"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())