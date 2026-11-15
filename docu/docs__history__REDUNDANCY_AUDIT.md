# Redundant PDF import candidate — NOT QUALIFIED

Three sequential source-PDF import approaches implemented in `chronoseal/pipeline.py`:
1. pypdf native page copy, only when no annotations exist.
2. PyMuPDF render-to-image visual flatten of each page.
3. PyMuPDF raster plus ReportLab PDF assembly.

The original PDF bytes are attached to the output after page footer composition. A visual reproduction is not a valid original cryptographic signature. Password-protected PDFs requiring a password still fail closed.

The existing suite run with `PYTHONPATH=. python -m pytest -q` returned **69 passed, 7 failed**. No real signed PDF end-to-end RFC3161 validation or Windows GUI validation was completed. Release remains BLOCKED.
