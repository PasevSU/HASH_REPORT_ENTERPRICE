"""Three independent read-only PDF assembly validators. Fail closed.

These are *checks*, not alternative writers: never rasterize or rewrite a signed
PDF in order to make a failed validation pass.
"""
from pathlib import Path

def validate_pdf(path, expected_pages=None):
    path = Path(path)
    checks = {}
    for name in ("pypdf", "pymupdf", "pdf_header"):
        try:
            if name == "pypdf":
                from pypdf import PdfReader
                r = PdfReader(str(path), strict=True)
                if r.is_encrypted: raise ValueError("encrypted PDF")
                count = len(r.pages)
                if not count: raise ValueError("no pages")
                checks[name] = {"pass": expected_pages is None or count == expected_pages, "pages": count}
            elif name == "pymupdf":
                import fitz
                with fitz.open(path) as d:
                    if d.needs_pass: raise ValueError("encrypted PDF")
                    count = len(d)
                    checks[name] = {"pass": count > 0 and (expected_pages is None or count == expected_pages), "pages": count}
            else:
                with path.open("rb") as f:
                    prefix = f.read(8)
                    f.seek(max(0, path.stat().st_size - 2048))
                    tail = f.read()
                checks[name] = {"pass": prefix.startswith(b"%PDF-") and b"%%EOF" in tail}
        except Exception as exc:
            checks[name] = {"pass": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"status": "PASS" if all(v["pass"] for v in checks.values()) else "FAILED", "checks": checks}
