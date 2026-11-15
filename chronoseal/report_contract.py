"""Shared evidence-section contract for SINGLE, COMBO, VOLUME and automation reports.
Read-only validation: no edits to signed evidence PDFs.
"""
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class Section:
    key: str
    title: str
    required: bool = True

COMMON = (
    Section('identity', 'Report ID'),
    Section('system', 'System Information'),
    Section('volume', 'Volume'),
    Section('user', 'User Information'),
    Section('hashes', 'SHA-256'),
    Section('timestamp', 'Cryptographic Timestamp'),
    Section('start', 'Cryptographic Timestamp START'),
    Section('stop', 'Cryptographic Timestamp STOP'),
    Section('legal', 'Rechtliche'),
    Section('document_hashes', 'TOTAL DOCUMENT TEXT CHECKSUMS'),
)
KIND = {
    'single': (Section('file', 'File Information'),),
    'combo': (Section('files', 'Evidence Package Files Information'),),
    'combo_all': (Section('files', 'Evidence Package Files Information'),),
    'single_pdf': (Section('file', 'File Information'),),
    'volume': (),
    'automation': (),
    'verification': (),
}

def inspect_pdf(path, kind='single'):
    import fitz
    # Every report kind declared by the shared theme/profile must be inspectable;
    # an unknown name is a programming error, not an empty section list.
    if kind not in KIND:
        raise ValueError(f'unknown report type: {kind}')
    with fitz.open(Path(path)) as doc:
        text = '\n'.join(page.get_text(sort=True) for page in doc)
        pages = len(doc)
    found = {}
    for s in (*COMMON, *KIND[kind]):
        found[s.key] = bool(re.search(re.escape(s.title), text, re.I))
    return {'kind': kind, 'pages': pages, 'sections': found,
            'missing': [k for k,v in found.items() if not v],
            'status': 'PASS' if all(found.values()) else 'REVIEW',
            'note': 'Text presence only; does not verify cryptographic claims or signatures'}
