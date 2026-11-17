"""ChronoSeal CLI edition - report-name orchestrator.

One word names the report, one argument names the input. The orchestrator only
validates the pair and translates the readable report name into the flags of
``chronoseal_cli.py``, so both front doors share one evidence path: session log,
environment snapshot, TSA trust bootstrap, the seal and the closing QR block.

Every report ends with a verification QR link built from the address given by
``--url`` plus a freshly generated code. That single address is expected to
redirect to two documents - the report itself and its proof bundle - which is the
part this package cannot do for you (see ``--information``).

Usage::

    python chronoseal_report.py list
    python chronoseal_report.py SINGLE   report.pdf   --url https://host/static/
    python chronoseal_report.py COMBO    D:\\in      --output-dir D:\\out
    python chronoseal_report.py COMBO    D:\\in      --filter '*.eml' --filter '*.pdf'
    python chronoseal_report.py COMBO    --file a.pdf --file sub\\b.pdf
    python chronoseal_report.py COMBO_ALL_PDF D:\\in --pdf cover.pdf --position before

Exit codes: 0 PASS, 2 BLOCKED (preflight/pipeline), 130 CANCELLED.
"""
import argparse, os, sys
from pathlib import Path

import chronoseal_cli

EXIT_USAGE = 2

# input kind -> flags. "embed" marks the reports that carry a second PDF.
REPORTS = {
    'SINGLE': ('file', {}, 'sealed hash report of one file'),
    'SINGLE_PDF': ('file', {'source_pdf': True},
                   'sealed hash report of one file with the input embedded byte-exact'),
    'COMBO': ('folder', {}, 'sealed hash report of every file in one folder'),
    'COMBO_PDF': ('folder', {'embed': True},
                  'sealed hash report of one folder with one PDF embedded before or after it'),
    'COMBO_ALL': ('folder', {'recursive': True},
                  'sealed hash report of a folder and all of its subfolders'),
    'COMBO_ALL_PDF': ('folder', {'recursive': True, 'embed': True},
                      'sealed hash report of a folder tree with one PDF embedded before or after it'),
}

INFORMATION = """\
ChronoSeal CLI edition - a package for adaptation, not a finished appliance.

Every report closes with a QR link: a verification address plus a code generated
for that one report. Before the link is usable, the address given with --url must
redirect that link to TWO documents:

  1. the sealed report this run produced (the PDF named on the PASS line), and
  2. the proof bundle for it - the timestamps, the OTS proof and the hashes.

This code creates neither the redirect nor a .ots file. It prints the link, the
report and the evidence folder, and the server side decides where the link lands.
One address, two documents, per report.
"""


class UsageError(ValueError):
    """Operator mistake phrased for the console; never a pipeline failure."""


def build_parser():
    parser = argparse.ArgumentParser(
        prog='chronoseal_report.py',
        description='Headless ChronoSeal: name the report, give the input, get sealed evidence.',
        epilog='Reports: ' + ', '.join(sorted(REPORTS)) + '. Run "chronoseal_report.py list" for '
               'the input each one expects, or "chronoseal_report.py --information" for the '
               'URL redirection this package expects.',
    )
    parser.add_argument('report', nargs='?', help='report name, e.g. SINGLE, COMBO_PDF, COMBO_ALL')
    parser.add_argument('target', nargs='?', help='the file (SINGLE*) or folder (COMBO*) to seal')
    parser.add_argument('--file', action='append', metavar='PATH', default=None, dest='files',
                        help='name one evidence file explicitly instead of scanning a folder; repeat '
                             'for a chosen set (COMBO reports only, the target folder becomes optional)')
    parser.add_argument('--filter', action='append', metavar='GLOB', default=None,
                        help='file-type filter for a folder report, e.g. "*.eml"; repeat to chain')
    parser.add_argument('--pdf', help='PDF to embed into the *_PDF reports (before or after the report)')
    parser.add_argument('--position', choices=['before', 'after'], default='after',
                        help='place the embedded PDF before or after the report (default: after)')
    parser.add_argument('--url', default='',
                        help='host that publishes the verification link (the run appends a '
                             'generated code); it must redirect to the report and its proof bundle')
    parser.add_argument('--output-dir', help='where the report and the evidence case are written')
    parser.add_argument('--explanation', action='store_true', help='embed ERLAEUTERUNG.pdf into the report')
    parser.add_argument('--preflight', action='store_true', help='run the checks only, then exit')
    parser.add_argument('--config', help='alternative config.json')
    parser.add_argument('--root', help='pipeline working root (default: the installation directory)')
    parser.add_argument('--log-dir', help='where session logs are written')
    parser.add_argument('--json', action='store_true', help='emit one JSON result on stdout')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--information', '--info', action='store_true', dest='information',
                        help='print what this edition expects around the verification URL, then exit')
    parser.add_argument('--version', action='store_true', help='print the version, then exit')
    return parser


def report_table():
    lines = []
    for name in sorted(REPORTS):
        kind, _, summary = REPORTS[name]
        expect = 'a file' if kind == 'file' else 'a folder'
        lines.append((name, expect, summary))
    width = max(len(name) for name, _, _ in lines)
    return '\n'.join('  %-*s  %-9s  %s' % (width, name, expect, summary) for name, expect, summary in lines)


def print_reports(stream=None):
    stream = stream or sys.stdout
    stream.write('Report names (the input decides the mode, the name decides the assembly):\n')
    stream.write(report_table() + '\n\n')
    stream.write(INFORMATION)


def build_argv(report, target, args):
    """Translate a report name plus an input into chronoseal_cli arguments."""
    kind, flags, _ = REPORTS[report]
    chosen = [Path(item).expanduser() for item in (args.files or [])]
    if chosen:
        if kind != 'folder':
            raise UsageError('%s seals exactly one file; an explicit file set belongs to COMBO' % report)
        if flags.get('recursive'):
            raise UsageError('%s walks a folder tree; an explicit file set already names the '
                             'evidence, so use %s' % (report, report.replace('_ALL', '')))
        if args.filter:
            raise UsageError('an explicit file set and file type filters cannot be combined: '
                             'the chosen files already are the evidence set')
        absent = [item for item in chosen if not item.is_file()]
        if absent:
            raise UsageError('selected file not found: %s' % absent[0])
    elif kind == 'file' and args.filter:
        raise UsageError('file type filters only apply to a folder report; %s seals one file' % report)

    path = Path(target).expanduser() if target else None
    if path is None:
        if not chosen:
            raise UsageError('%s needs %s to seal' % (report, 'a file' if kind == 'file' else 'a folder'))
        path = common_root(chosen)
    elif kind == 'file' and not path.is_file():
        raise UsageError('%s needs an existing file, not %s' % (report, target))
    elif kind == 'folder' and not path.is_dir():
        raise UsageError('%s needs an existing folder, not %s' % (report, target))

    pdf = None
    if flags.get('embed'):
        if not args.pdf:
            raise UsageError('%s embeds a PDF; pass it with --pdf' % report)
        pdf = Path(args.pdf).expanduser()
        if not pdf.is_file():
            raise UsageError('embedded PDF not found: %s' % args.pdf)
    elif args.pdf:
        raise UsageError('%s does not embed a second PDF; use %s_PDF' % (report, report))

    argv = [str(path), '--mode', 'single' if kind == 'file' else 'combined']
    if flags.get('recursive'):
        argv.append('--recursive')
    if flags.get('source_pdf'):
        argv.append('--source-pdf')
    for item in chosen:
        argv += ['--file', str(item)]
    for pattern in args.filter or []:
        argv += ['--filter', pattern]
    if pdf is not None:
        argv += ['--embed-pdf', str(pdf), '--embed-position', args.position]
    for flag, value in (('--url', args.url), ('--output-dir', args.output_dir),
                        ('--config', args.config), ('--root', args.root), ('--log-dir', args.log_dir)):
        if value:
            argv += [flag, str(value)]
    for flag, given in (('--explanation', args.explanation), ('--preflight', args.preflight),
                        ('--json', args.json), ('--quiet', args.quiet)):
        if given:
            argv.append(flag)
    return argv


def common_root(paths):
    """Deepest folder that contains every chosen file; the report's evidence root."""
    parents = [str(Path(item).resolve().parent) for item in paths]
    try:
        root = os.path.commonpath(parents)
    except ValueError as exc:
        raise UsageError('all selected files must live on one drive: %s' % exc) from exc
    return Path(root)


def version():
    try:
        from chronoseal.branding import VERSION
    except Exception:
        return 'unknown'
    return VERSION


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].lower() in ('list', '--list', '--list-reports'):
        print_reports()
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.information:
        sys.stdout.write(INFORMATION)
        return 0
    if args.version:
        sys.stdout.write('ChronoSeal CLI edition %s\n' % version())
        return 0
    if not args.report:
        parser.print_help(sys.stderr)
        sys.stderr.write('\nBLOCKED: name the report first, e.g. "SINGLE file.pdf".\n')
        return EXIT_USAGE
    report = args.report.upper()
    if report not in REPORTS:
        sys.stderr.write('BLOCKED: unknown report "%s". Known names:\n%s\n'
                         % (args.report, report_table()))
        return EXIT_USAGE
    try:
        argv = build_argv(report, args.target, args)
    except UsageError as exc:
        sys.stderr.write('BLOCKED: %s\n' % exc)
        return EXIT_USAGE
    return chronoseal_cli.main(argv)


if __name__ == '__main__':
    sys.exit(main())
