"""Read-only A4 quality gate for manual and automated ChronoSeal PDF reports.

Visual/layout validation is NOT a cryptographic signature verification.
"""
from pathlib import Path
import json

from .unified_report_profile import DEFAULT_PROFILE

MM = 72 / 25.4
A4 = (210 * MM, 297 * MM)

# The audit defaults are the shared profile, so the gate can never drift away
# from the geometry the generator actually produces.
_DEFAULTS = DEFAULT_PROFILE.audit_options()

# Appendix pages declare themselves with their canonical title from the style
# rules, so the audit never has to guess a page index.
_APPENDIX_TITLES = None


def _appendix_titles():
    global _APPENDIX_TITLES
    if _APPENDIX_TITLES is None:
        try:
            from hash_report_generator.style_loader import load_styles
            rules = load_styles()['PAGE_IDENTITY']
            _APPENDIX_TITLES = tuple(
                rules[key] for key in
                ('document_appendix_title', 'combined_appendix_title', 'source_appendix_title')
                if rules.get(key)
            )
        except Exception:
            # Do not cache a transient failure (e.g. Node busy during style
            # loading): a later audit in the same process must be able to retry
            # instead of permanently treating every page as non-appendix.
            return ()
    return _APPENDIX_TITLES


def audit_layout(path, *, left_mm=_DEFAULTS['left_mm'], right_mm=_DEFAULTS['right_mm'],
                 top_mm=_DEFAULTS['top_mm'], bottom_mm=_DEFAULTS['bottom_mm'],
                 footer_band_mm=_DEFAULTS['footer_band_mm'],
                 appendix_top_mm=_DEFAULTS['appendix_top_mm'],
                 minimum_body_words=_DEFAULTS['minimum_body_words']):
    import fitz
    path = Path(path)
    issues, pages = [], []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, 1):
            r = page.rect
            a4 = abs(r.width - A4[0]) < 2 and abs(r.height - A4[1]) < 2
            if not a4:
                issues.append(f'page {index}: not A4')
            words = page.get_text('words')
            raw_text = page.get_text('text')
            # The checksum appendix is a declared layout of its own: its title is
            # set above the body frame, so it uses the appendix top allowance.
            appendix = any(title in raw_text for title in _appendix_titles())
            page_top_mm = appendix_top_mm if appendix else top_mm
            # Footer is audited separately: it is intentionally below the body area.
            body = [w for w in words if w[1] < r.height - footer_band_mm * MM]
            footer = [w for w in words if w[1] >= r.height - footer_band_mm * MM]
            tolerance_pt = 0.1
            body_outside = [w for w in body if (
                w[0] < left_mm*MM-tolerance_pt
                or w[2] > r.width-right_mm*MM+tolerance_pt
                or w[1] < page_top_mm*MM-tolerance_pt
                or w[3] > r.height-bottom_mm*MM+tolerance_pt
            )]
            footer_outside = [w for w in footer if (
                w[0] < 5*MM-tolerance_pt
                or w[2] > r.width-5*MM+tolerance_pt
                or w[3] > r.height-3*MM+tolerance_pt
            )]
            # Three independent read-only probes: word extraction, raw text, and
            # content-stream drawings/images. None may certify a signature.
            # A blank page is REVIEW even if the other probes disagree.
            probes = {}
            probe_errors = {}
            for probe in ('words', 'text', 'graphics'):
                try:
                    if probe == 'words':
                        probes[probe] = bool(words)
                    elif probe == 'text':
                        probes[probe] = bool(raw_text.strip())
                    else:
                        # Drawings/images are meaningful visual content; do not
                        # treat invisible PDF operators as proof of visible text.
                        probes[probe] = bool(page.get_drawings() or page.get_images(full=True))
                except Exception as exc:
                    probe_errors[probe] = type(exc).__name__ + ': ' + str(exc)
            if not probes.get('words') and not probes.get('text'):
                issues.append(f'page {index}: no extractable text')
            if probe_errors:
                issues.append(f'page {index}: probe failures {probe_errors}')
            if len(body) < minimum_body_words:
                issues.append(f'page {index}: sparse or empty body ({len(body)} words)')
            if body_outside:
                issues.append(f'page {index}: {len(body_outside)} body words outside content margins')
            if footer_outside:
                issues.append(f'page {index}: {len(footer_outside)} footer words outside safe page edges')
            pages.append(dict(page=index, a4=a4, appendix=appendix, body_words=len(body), footer_words=len(footer),
                              body_margin_violations=len(body_outside), footer_edge_violations=len(footer_outside), content_probes=probes, probe_errors=probe_errors))
    return dict(file=str(path), status='PASS' if not issues else 'REVIEW', issues=issues, pages=pages,
                note='Layout-only check; does not verify PDF signatures, timestamps, or legal compliance')


def audit_many(paths):
    return {'reports': [audit_layout(p) for p in paths]}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read-only ChronoSeal PDF layout gate')
    parser.add_argument('pdf', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit_many(args.pdf)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    else:
        print(output)
    raise SystemExit(1 if any(r['status'] != 'PASS' for r in result['reports']) else 0)
