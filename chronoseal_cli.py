"""Headless ChronoSeal runner.

Same evidence path as the GUI: session log, environment snapshot, command
records, automatic TSA trust bootstrap and the transactional seal. Designed to
be driven by Task Scheduler or a shell without a display.

Exit codes: 0 PASS, 2 BLOCKED (preflight/pipeline), 130 CANCELLED.
"""
import argparse, copy, json, signal, sys, threading, traceback
from pathlib import Path

from chronoseal.logging_bundle import SessionLogger
from chronoseal.pipeline import Pipeline, PipelineError, Cancelled
from chronoseal.provider_bootstrap import bootstrap_providers, BootstrapError
from chronoseal.settings import executable, load, save
from chronoseal import selfheal

BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / 'config' / 'config.json'
EXIT_PASS, EXIT_BLOCKED, EXIT_CANCELLED = 0, 2, 130


def parse(argv):
    p = argparse.ArgumentParser(prog='chronoseal_cli.py', description='Headless ChronoSeal hash report + RFC3161 seal.')
    p.add_argument('target', nargs='?', help='file or directory to seal')
    p.add_argument('--mode', choices=['single', 'combined'], default=None, help='advisory; the input kind is detected from the target')
    p.add_argument('--recursive', action='store_true')
    p.add_argument('--root', default=str(BASE),
                   help='pipeline working root for config-relative assets (default: the ChronoSeal installation directory)')
    p.add_argument('--config', default=str(CFG_PATH))
    p.add_argument('--log-dir', default=str(BASE / 'logs'), help='where session logs are written')
    p.add_argument('--explanation', action='store_true', help='embed ERLAEUTERUNG.pdf into the report')
    p.add_argument('--source-pdf', action='store_true', help='embed the original PDF (SINGLE only)')
    p.add_argument('--embed-pdf', help='embed this PDF into a COMBO report (visible pages + byte-exact attachment)')
    p.add_argument('--embed-position', choices=['before', 'after'], default='after',
                   help='place the embedded PDF before or after the hash report (default: after)')
    p.add_argument('--qr-url', default='',
                   help='override the generated closing-QR link with this http(s) address; '
                        'the block itself is always printed and the link is otherwise '
                        'generated from the configured base address plus a random code')
    p.add_argument('--output-dir')
    p.add_argument('--preflight', action='store_true', help='run checks only, then exit')
    p.add_argument('--self-check', action='store_true', help='verify and repair dependencies only, then exit')
    p.add_argument('--repair-network', action='store_true', help='allow pip/npm to reach the network while repairing')
    p.add_argument('--bootstrap-trust', action='store_true', help='refresh TSA trust material only, then exit')
    p.add_argument('--json', action='store_true', help='emit one JSON result on stdout (logs go to stderr)')
    p.add_argument('--quiet', action='store_true')
    return p.parse_args(argv)


def make_emitter(quiet, json_mode):
    stream = sys.stderr if json_mode else sys.stdout
    def emit(line):
        if quiet:
            return
        try:
            stream.write(str(line).rstrip() + '\n'); stream.flush()
        except (OSError, ValueError):
            pass
    return emit


def main(argv=None):
    args = parse(argv)
    emit = make_emitter(args.quiet, args.json)
    result = {'status': 'BLOCKED', 'target': args.target, 'session_dir': None, 'final_pdf': None, 'error': None}
    code = EXIT_BLOCKED
    cfg_path = Path(args.config)
    session = None
    failure = None
    cancel = threading.Event()

    def on_sigint(signum, frame):
        # First Ctrl+C asks the watchdog to stop the child; a second one aborts hard.
        if cancel.is_set():
            raise KeyboardInterrupt
        cancel.set(); emit('Cancellation requested — stopping the child process…')
    try:
        signal.signal(signal.SIGINT, on_sigint)
    except (ValueError, OSError):
        pass

    try:
        cfg = load(cfg_path)
        if args.repair_network:
            cfg.setdefault('repair', {})['allow_network'] = True
        pipeline = Pipeline(args.root, cfg, emit, session, cancel_event=cancel)
        if args.self_check:
            report = selfheal.self_check(args.root, cfg, emit, allow_network=args.repair_network)
            for action in report['actions']:
                emit('[SELF-HEAL] %s' % json.dumps(action, ensure_ascii=False))
            for problem in report['problems']:
                emit('BLOCKER: ' + problem)
            emit('SELF-CHECK ' + ('PASS' if report['ok'] else 'BLOCKED'))
            result.update(status='PASS' if report['ok'] else 'BLOCKED', self_check=report, issues=report['problems'])
            return finish(result, emit, args.json, EXIT_PASS if report['ok'] else EXIT_BLOCKED)
        if args.bootstrap_trust:
            openssl = executable('openssl', (cfg.get('tools') or {}).get('openssl'))
            if not openssl:
                raise BootstrapError('OpenSSL is required for TSA trust bootstrap')
            report, updated = bootstrap_providers(BASE, copy.deepcopy(cfg), openssl)
            save(cfg_path, updated)
            emit('[TRUST] ' + json.dumps(report, ensure_ascii=False))
            result.update(status='PASS', trust=report)
            return finish(result, emit, args.json, EXIT_PASS)
        if not args.target:
            raise PipelineError('No target given. Pass a file or directory, or use --preflight / --self-check / --bootstrap-trust.')
        if args.preflight:
            info, issues, warnings = pipeline.preflight(Path(args.target).expanduser(),
                                                       pdf_embed=args.source_pdf,
                                                       combo_embed=bool(args.embed_pdf))
            for key, value in info.items():
                emit(f'  {key}: {value}')
            for warning in warnings:
                emit('WARNING: ' + warning)
            for issue in issues:
                emit('BLOCKER: ' + issue)
            emit('PREFLIGHT ' + ('PASS' if not issues else 'BLOCKED'))
            result.update(status='PASS' if not issues else 'BLOCKED', preflight=info, issues=issues, warnings=warnings)
            return finish(result, emit, args.json, EXIT_PASS if not issues else EXIT_BLOCKED)

        session = SessionLogger(Path(args.log_dir), emit)
        result['session_dir'] = str(session.dir)
        session.snapshot(BASE, cfg)
        pipeline.session = session
        policy = cfg.get('rfc3161', {})
        missing = any(not (p.get('trust_root_files') or []) for stage in ('start', 'stop') for p in policy.get(stage, []))
        if missing:
            session.write('[TRUST] Missing TSA trust material — automatic bootstrap started')
            openssl = executable('openssl', (cfg.get('tools') or {}).get('openssl'))
            if not openssl:
                raise BootstrapError('OpenSSL is required for TSA trust bootstrap')
            report, updated = bootstrap_providers(BASE, copy.deepcopy(cfg), openssl)
            save(cfg_path, updated)
            pipeline.cfg = cfg = updated
            session.write('[TRUST] ' + json.dumps(report, ensure_ascii=False))
            session.write('[TRUST] automatic bootstrap PASS')
        summary = pipeline.run(Path(args.target).expanduser(), args.mode or 'combined', args.recursive,
                               args.explanation, args.source_pdf, args.output_dir,
                               embed_pdf=Path(args.embed_pdf).expanduser() if args.embed_pdf else None,
                               embed_position=args.embed_position,
                               qr_url=args.qr_url)
        session.write('FINAL PASS')
        result.update(status='PASS', final_pdf=summary.get('final_pdf'), summary=summary)
        code = EXIT_PASS
    except Cancelled as exc:
        failure = exc; result.update(status='CANCELLED', error=str(exc)); code = EXIT_CANCELLED
    except (PipelineError, BootstrapError, OSError, ValueError) as exc:
        failure = exc; result.update(status='BLOCKED', error=f'{type(exc).__name__}: {exc}'); code = EXIT_BLOCKED
    except KeyboardInterrupt as exc:
        failure = exc; result.update(status='CANCELLED', error='Interrupted by user'); code = EXIT_CANCELLED
    except Exception as exc:
        # An unexpected failure must still honour the documented 0/2/130 contract
        # and leave a machine-readable result; the traceback goes to stderr and
        # to error.txt so nothing is lost for debugging.
        failure = exc
        result.update(status='BLOCKED', error=f'{type(exc).__name__}: {exc}')
        code = EXIT_BLOCKED
        traceback.print_exc(file=sys.stderr)
    finally:
        if session is not None:
            if result['error'] and failure is not None and not isinstance(failure, KeyboardInterrupt):
                session.error(failure)
            result['session_dir'] = str(session.dir)
    return finish(result, emit, args.json, code)


def finish(result, emit, json_mode, code):
    if json_mode:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + '\n'); sys.stdout.flush()
    elif result.get('status') == 'PASS':
        emit('PASS ' + str(result.get('final_pdf') or ''))
    elif result.get('error'):
        emit(result['status'] + ': ' + result['error'])
    if result.get('session_dir'):
        emit('Log: ' + result['session_dir'])
    return code


if __name__ == '__main__':
    sys.exit(main())
