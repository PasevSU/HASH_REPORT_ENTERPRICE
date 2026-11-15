"""Expert-audit hardening guards.

Every test here locks in a defect found by the deep audit:

* no captured child process may inherit an invalid stdin (the ``pythonw.exe``
  failure mode that once reported a healthy Node package as missing);
* the environment snapshot must query each tool exactly once;
* the legacy startup path must use the same offline, hash-pinned repair policy
  as the pipeline instead of silently running a network install;
* RFC3161 stamping must run under a bounded budget and stream progress;
* an interrupted archive must never leave a published folder without a database
  row (that would block the report number forever);
* the ``config.evidence`` retention switches must be enforced rather than
  accepted and silently ignored.
"""
import ast
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / 'chronoseal'


class CapturedSubprocessStdinTests(unittest.TestCase):
    """A child that inherits pythonw's invalid stdin can fail for no reason."""

    def _calls(self):
        for path in sorted(PACKAGE.glob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ('run', 'Popen', 'check_output', 'check_call')
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'subprocess'):
                    yield path.name, node

    def test_every_child_gets_explicit_stdin(self):
        offenders = []
        for name, node in self._calls():
            keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
            if 'stdin' not in keywords:
                offenders.append(f'{name}:{node.lineno}')
        self.assertEqual(offenders, [], 'child processes without stdin=DEVNULL: ' + ', '.join(offenders))

    def test_no_console_window_is_created(self):
        offenders = []
        for name, node in self._calls():
            keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
            if 'windowsHide' not in keywords and 'creationflags' not in keywords:
                offenders.append(f'{name}:{node.lineno}')
        self.assertEqual(offenders, [], 'child processes may flash a console window: ' + ', '.join(offenders))


    def test_no_unsupported_windowsHide_keyword(self):
        # This Python build's Popen has no ``windowsHide`` parameter; passing it
        # raises TypeError before the child even starts. CREATE_NO_WINDOW is used.
        offenders = []
        for name, node in self._calls():
            keywords = {keyword.arg for keyword in node.keywords if keyword.arg}
            if 'windowsHide' in keywords:
                offenders.append(f'{name}:{node.lineno}')
        self.assertEqual(offenders, [], 'unsupported windowsHide keyword: ' + ', '.join(offenders))


class SessionSnapshotTests(unittest.TestCase):
    def test_each_tool_is_queried_exactly_once(self):
        from chronoseal.logging_bundle import SessionLogger
        calls = []

        class Result:
            def __init__(self, stdout, stderr):
                self.stdout, self.stderr, self.returncode = stdout, stderr, 0

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            return Result('', 'openssl 4.0.3') if 'version' in args else Result('v26.13.0', '')

        with tempfile.TemporaryDirectory() as base:
            logger = SessionLogger(base)
            with patch('chronoseal.logging_bundle.subprocess.run', side_effect=fake_run):
                data = logger.snapshot(base, {'tools': {'node': 'node', 'openssl': 'openssl'}})
        self.assertEqual(len(calls), 2, f'expected one probe per tool, got {len(calls)}')
        self.assertEqual(data['node'], 'v26.13.0')
        self.assertEqual(data['openssl'], 'openssl 4.0.3')
        for args, kwargs in calls:
            self.assertIs(kwargs.get('stdin'), subprocess.DEVNULL, f'{args} inherited stdin')


class StartupRepairPolicyTests(unittest.TestCase):
    """startup.py must not bypass repair.allow_network with npm install."""

    def _broken_root(self, base):
        import shutil
        base = Path(base)
        shutil.copytree(ROOT / 'vendor' / 'pdf-rfc3161', base / 'vendor' / 'pdf-rfc3161')
        target = base / 'node_modules' / 'pdf-rfc3161'
        shutil.copytree(ROOT / 'vendor' / 'pdf-rfc3161', target)
        (target / 'dist' / 'index.js').unlink()
        return base

    def test_broken_package_is_repaired_from_vendor_without_network(self):
        from chronoseal.startup import startup_check
        from chronoseal import selfheal

        def fake_run(cmd, *args, **kwargs):
            self.assertNotIn('install', [str(part) for part in cmd],
                             'startup must not run a network install when repair.allow_network is false')
            return 0, ''

        with tempfile.TemporaryDirectory() as base:
            root = self._broken_root(base)
            cfg = {'tools': {'node': 'node'},
                   'repair': {'enabled': True, 'allow_network': False}}
            with (patch('chronoseal.startup.executable', side_effect=lambda name, configured=None: configured),
                  patch('chronoseal.startup.node_version', return_value=(22, 12, 0)),
                  patch('chronoseal.startup._run', side_effect=fake_run)):
                report, _ = startup_check(root, cfg, False)
            self.assertIn('pdf_rfc3161_state_before', report['checks'])
            self.assertEqual(report['checks']['pdf_rfc3161_state_before'], 'BROKEN')
            self.assertTrue(selfheal.node_package_state(root)['state'] == 'OK')
            self.assertFalse([b for b in report['blockers'] if 'pdf-rfc3161' in b], report['blockers'])

    def test_network_install_requires_explicit_consent(self):
        from chronoseal.startup import startup_check

        def fake_run(cmd, *args, **kwargs):
            return 0, ''

        with tempfile.TemporaryDirectory() as base:
            cfg = {'tools': {'node': 'node'},
                   'repair': {'enabled': True, 'allow_network': True}}
            with (patch('chronoseal.startup.executable', side_effect=lambda name, configured=None: configured),
                  patch('chronoseal.startup.node_version', return_value=(22, 12, 0)),
                  patch('chronoseal.startup._run', side_effect=fake_run) as run,
                  patch('chronoseal.selfheal.npm_install', return_value=True) as npm):
                report, _ = startup_check(Path(base), cfg, True)
            self.assertTrue(npm.called, 'consented repair may fall back to the registry')
            self.assertTrue(any('npm install' in str(a) for a in report['actions']), report['actions'])


class StampBudgetTests(unittest.TestCase):
    def _pipeline(self):
        from chronoseal.pipeline import Pipeline
        config = {'rfc3161': {}}
        pipeline = Pipeline(ROOT, config)
        pipeline.log = lambda message: None
        return pipeline

    def test_stamp_runs_under_a_bounded_budget(self):
        pipeline = self._pipeline()
        pipeline.cfg['rfc3161']['timeout_seconds'] = 1800
        pipeline.cfg['rfc3161']['idle_timeout_seconds'] = 600
        with tempfile.TemporaryDirectory() as case, patch.object(
                pipeline, '_run', side_effect=AssertionError('stop')) as run:
            source = Path(case) / 'in.pdf'
            from pypdf import PdfWriter
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with source.open('wb') as stream:
                writer.write(stream)
            with self.assertRaises(AssertionError):
                pipeline.stamp(source, Path(case))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs.get('timeout'), 1800.0)
        self.assertEqual(kwargs.get('idle_timeout'), 600.0)
        self.assertTrue(kwargs.get('stream'), 'a long stamp must stream progress')


class QualifiedTrustScopeTests(unittest.TestCase):
    """One provider's trust anchors must never leak into the next validation."""

    def _run_validation(self, roots, seen):
        from chronoseal import qualified_validation as qv

        config = {
            'tools': {'openssl': 'openssl'},
            'rfc3161': {'trusted_list_validation': {
                'lotl_file': 'trust/LOTL/eu-lotl.xml',
                'lotl_signer_certificate_file': 'trust/LOTL/signer.pem',
                'lotl_signer_sha256': 'A' * 64,
                'member_tsl_file': 'trust/LOTL/tsl-bg.xml',
                'member_tsl_url': 'https://example.invalid/tsl-bg.xml',
            }},
        }
        identity = 'AB' * 32
        provider = {
            'name': 'Test QTSA', 'qualified': True,
            'trusted_list_service_status': 'granted',
            'service_access_confirmed': True, 'auth': 'none',
            'trust_root_files': roots,
            'trusted_list_service_certificate_sha256': identity,
        }

        def fake_token(**kwargs):
            seen.append({key: qv.os.environ.get(key) for key in qv._TRUST_ENV})
            return {
                'certificate_path_sha256': [identity],
                'chain': {'status': 'GOOD'},
                'root_trust_status': 'PASS (explicitly configured trust root)',
                'crl': {'status': 'GOOD'}, 'ocsp': {},
                'signer_sha256': identity, 'root_sha256': identity,
                'artifacts': [],
            }

        with tempfile.TemporaryDirectory() as base:
            with (patch.object(qv, 'verify_lotl_and_member_tsl', return_value={'status': 'SIGNATURE_VALID'}),
                  patch.object(qv, 'verify_qualified_tsa_service_status',
                               return_value={'identity_sha256': identity}),
                  patch.object(qv, 'validate_rfc3161_token', side_effect=fake_token)):
                return qv.validate_qualified_timestamp(
                    token_der=b'token', gen_time='2026-01-01T00:00:00Z', config=config,
                    provider=provider, project_root=ROOT, evidence_dir=Path(base) / 'evidence')

    def test_anchors_are_scoped_to_one_call_and_restored(self):
        from chronoseal import qualified_validation as qv
        for key in qv._TRUST_ENV:
            os.environ.pop(key, None)
        seen = []
        self._run_validation(['trust/first.pem'], seen)
        self.assertEqual(seen[0][qv._TRUST_ENV[0]], json.dumps([str((ROOT / 'trust/first.pem').resolve())]))
        self.assertIsNone(os.environ.get(qv._TRUST_ENV[0]), 'trust roots leaked out of the validation call')
        self.assertIsNone(os.environ.get(qv._TRUST_ENV[1]))

        self._run_validation(['trust/second.pem'], seen)
        self.assertNotIn('first.pem', seen[1][qv._TRUST_ENV[0]],
                         'the previous provider anchors leaked into the next validation')


class CliFailureContractTests(unittest.TestCase):
    """An unexpected error must still return a documented exit code and JSON."""

    def test_unexpected_error_is_blocked_not_a_traceback_exit(self):
        import chronoseal_cli as cli
        import contextlib
        import io

        class Boom(cli.Pipeline):
            def __init__(self, *args, **kwargs):
                self.cfg = args[1] if len(args) > 1 else {}
                self.session = None

            def run(self, *args, **kwargs):
                raise RuntimeError('internal invariant violated')

        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as base:
            with patch.object(cli, 'Pipeline', Boom), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                code = cli.main([base, '--json', '--log-dir', str(Path(base) / 'logs')])
            payload = json.loads(out.getvalue())
            self.assertEqual(code, cli.EXIT_BLOCKED)
            self.assertEqual(payload['status'], 'BLOCKED')
            self.assertIn('RuntimeError', payload['error'])
            self.assertIn('Traceback', err.getvalue(), 'the traceback must stay visible for debugging')
            self.assertTrue(Path(payload['session_dir'], 'error.txt').is_file())


class SignatureInventoryTests(unittest.TestCase):
    """A signature must never disappear from the inventory."""

    def _build(self, path, shared):
        from pypdf import PdfWriter
        from pypdf.generic import (ArrayObject, ByteStringObject, DictionaryObject,
                                   NameObject, NumberObject, TextStringObject)
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)

        def signature(byte_range):
            entry = DictionaryObject()
            entry[NameObject('/Type')] = NameObject('/Sig')
            entry[NameObject('/Filter')] = NameObject('/Adobe.PPKLite')
            entry[NameObject('/SubFilter')] = NameObject('/ETSI.RFC3161')
            entry[NameObject('/ByteRange')] = ArrayObject([NumberObject(v) for v in byte_range])
            entry[NameObject('/M')] = TextStringObject("D:20261107020000+01'00'")
            entry[NameObject('/Contents')] = ByteStringObject(b'\x00' * 8)
            return writer._add_object(entry)

        first = signature([0, 100, 200, 100])
        second = first if shared else signature([0, 300, 400, 500])
        field = DictionaryObject()
        field[NameObject('/FT')] = NameObject('/Sig')
        field[NameObject('/T')] = TextStringObject('ChronoSeal-Timestamp')
        field[NameObject('/V')] = first
        writer._root_object[NameObject('/AcroForm')] = DictionaryObject(
            {NameObject('/Fields'): ArrayObject([writer._add_object(field)])})
        writer._root_object[NameObject('/Perms')] = DictionaryObject(
            {NameObject('/DocTimeStamp'): second})
        with open(path, 'wb') as stream:
            writer.write(stream)

    def test_one_signature_reachable_twice_is_counted_once(self):
        from chronoseal.pdf_preflight import inspect_pdf
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / 'shared.pdf'
            self._build(path, shared=True)
            state = inspect_pdf(path)
            self.assertTrue(state['signed'])
            self.assertEqual(len(state['signatures']), 1, 'the same signature was inventoried twice')

    def test_distinct_signatures_are_all_inventoried(self):
        from chronoseal.pdf_preflight import inspect_pdf
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / 'distinct.pdf'
            self._build(path, shared=False)
            state = inspect_pdf(path)
            self.assertEqual(len(state['signatures']), 2, 'a signature was silently dropped')
            self.assertEqual({s['source'] for s in state['signatures']}, {'acroform', 'catalog/DocTimeStamp'})


class EvidenceCaseCreationTests(unittest.TestCase):
    """A blocked evidence folder must fail as an actionable PipelineError."""

    def test_blocked_evidence_folder_is_actionable(self):
        from chronoseal.pipeline import Pipeline, PipelineError
        with tempfile.TemporaryDirectory() as base:
            blocker = Path(base) / 'ChronoSeal_Evidence'
            blocker.write_text('occupied', encoding='utf-8')
            pipeline = Pipeline(ROOT, {'rfc3161': {}}, log=lambda *_: None)
            with self.assertRaises(PipelineError) as caught:
                pipeline._make_case_dir(blocker)
            message = str(caught.exception)
            self.assertIn('ChronoSeal_Evidence', message)
            self.assertIn('writable', message)


class StorageCapacityWarningTests(unittest.TestCase):
    """Free space is checked before the seal instead of failing halfway."""

    def test_low_space_is_reported(self):
        from chronoseal.storage_identity import low_space_warning
        message = low_space_warning({'bytes_available': 1024, 'probed_directory': 'X:\\data'})
        self.assertIsNotNone(message)
        self.assertIn('X:\\data', message)

    def test_plenty_of_space_is_silent(self):
        from chronoseal.storage_identity import low_space_warning
        self.assertIsNone(low_space_warning({'bytes_available': 10 ** 12}))
        self.assertIsNone(low_space_warning({}))

    def test_threshold_is_configurable_and_can_be_disabled(self):
        from chronoseal.storage_identity import low_space_warning
        identity = {'bytes_available': 50 * 1024 * 1024}
        self.assertIsNotNone(low_space_warning(identity, 100 * 1024 * 1024))
        self.assertIsNone(low_space_warning(identity, 10 * 1024 * 1024))
        self.assertIsNone(low_space_warning(identity, 0), 'a zero threshold must disable the check')


class ArchiveCleanupMaskingTests(unittest.TestCase):
    """A failing cleanup must not replace the real error."""

    def test_cleanup_failure_does_not_mask_the_primary_error(self):
        from chronoseal import report_archive
        with tempfile.TemporaryDirectory() as base:
            root = Path(base) / 'archive'
            pdf = Path(base) / 'RPT-1_HASHREPORT_TYP_COMBO.pdf'
            pdf.write_bytes(b'%PDF-1.7\n%%EOF\n')
            evidence = Path(base) / 'evidence'
            evidence.mkdir()
            (evidence / 'manifest.json').write_text('{}', encoding='utf-8')
            real_rmtree = report_archive.shutil.rmtree
            calls = []

            def rmtree(path, ignore_errors=False, onerror=None):
                calls.append((str(path), ignore_errors))
                if not ignore_errors:
                    raise PermissionError('locked by antivirus')
                return real_rmtree(path, ignore_errors=True)

            with patch.object(report_archive.sqlite3, 'connect',
                              side_effect=sqlite3.OperationalError('database is locked')), \
                    patch.object(report_archive.shutil, 'rmtree', side_effect=rmtree):
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    report_archive.archive_report(
                        archive_root=root, database_path=Path(base) / 'a.sqlite3',
                        report_pdf=pdf, evidence_directory=evidence, run_log=None,
                        manifest={}, report_name=pdf.name)
            self.assertIn('database is locked', str(caught.exception))
            self.assertTrue(calls, 'the staging folder was never cleaned up')
            self.assertTrue(all(ignore_errors for _, ignore_errors in calls),
                            'staging cleanup may not raise and mask the primary error')
            self.assertEqual([p for p in root.iterdir()], [], 'a partial staging folder survived')


class ReportContractKindTests(unittest.TestCase):
    """Every report kind declared by the theme must be inspectable."""

    def test_all_shared_report_kinds_have_a_contract(self):
        from chronoseal import report_contract, unified_theme
        missing = [kind for kind in unified_theme.REPORT_KINDS if kind not in report_contract.KIND]
        self.assertEqual(missing, [], 'declared report kinds without a section contract')

    def test_unknown_kind_is_still_rejected(self):
        from chronoseal.report_contract import inspect_pdf
        with self.assertRaises(ValueError):
            inspect_pdf('not-used.pdf', 'unknown')


class ThemeInvariantTests(unittest.TestCase):
    """The layout invariant must survive `python -O`."""

    def test_impossible_margins_raise_instead_of_asserting(self):
        from chronoseal.unified_theme import Theme
        with self.assertRaises(ValueError):
            Theme(margin_left_mm=120, margin_right_mm=120).validate()


class ArchiveInterruptTests(unittest.TestCase):
    def test_interrupt_after_publish_removes_the_orphan_folder(self):
        from chronoseal import report_archive

        class Connection:
            def execute(self, *args, **kwargs):
                return self

            def executescript(self, *args, **kwargs):
                return self

            def fetchone(self):
                return None

            def commit(self):
                raise KeyboardInterrupt('user pressed Ctrl+C')

            def rollback(self):
                self.rolled_back = True

            def close(self):
                pass

        connection = Connection()
        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            pdf = base / 'RPT-20260101-1-AB_HASHREPORT_TYP_SINGLE.pdf'
            pdf.write_bytes(b'%PDF-1.7\n%%EOF\n')
            evidence = base / 'evidence'
            evidence.mkdir()
            (evidence / 'manifest.json').write_text('{}', encoding='utf-8')
            archive_root = base / 'archive'
            with patch.object(report_archive.sqlite3, 'connect', return_value=connection):
                with self.assertRaises(KeyboardInterrupt):
                    report_archive.archive_report(
                        archive_root=archive_root,
                        database_path=base / 'archive.sqlite3',
                        report_pdf=pdf,
                        evidence_directory=evidence,
                        run_log=None,
                        manifest={'report_id': 'RPT-20260101-1-AB'},
                        report_name=pdf.name,
                    )
            self.assertFalse((archive_root / 'RPT-20260101-1-AB').exists(),
                             'an interrupted archive must not keep a published folder without a row')
            self.assertEqual(list(archive_root.glob('.RPT-*')), [], 'staging directory was left behind')

    def test_a_transient_windows_sharing_violation_on_publish_is_retried(self):
        from chronoseal import report_archive

        real_rename = os.rename
        calls = []

        def flaky_rename(source, destination):
            calls.append(str(destination))
            if len(calls) == 1:
                error = PermissionError(13, 'Access is denied', str(destination))
                error.winerror = 32
                raise error
            return real_rename(source, destination)

        with tempfile.TemporaryDirectory() as base:
            base = Path(base)
            pdf = base / 'RPT-20260101-2-AB_HASHREPORT_TYP_SINGLE.pdf'
            pdf.write_bytes(b'%PDF-1.7\n%%EOF\n')
            evidence = base / 'evidence'
            evidence.mkdir()
            (evidence / 'manifest.json').write_text('{}', encoding='utf-8')
            archive_root = base / 'archive'
            with patch.object(report_archive.os, 'rename', side_effect=flaky_rename):
                result = report_archive.archive_report(
                    archive_root=archive_root,
                    database_path=base / 'archive.sqlite3',
                    report_pdf=pdf,
                    evidence_directory=evidence,
                    run_log=None,
                    manifest={'report_id': 'RPT-20260101-2-AB'},
                    report_name=pdf.name,
                )
            self.assertEqual(len(calls), 2, 'a transient lock on publish must be retried')
            self.assertTrue(Path(result['archive_directory']).is_dir())


class EvidenceRetentionPolicyTests(unittest.TestCase):
    """config.evidence switches used to be accepted and silently ignored."""

    def test_the_shipped_config_is_accepted(self):
        from chronoseal import settings
        config = json.loads((ROOT / 'config' / 'config.json').read_text(encoding='utf-8'))
        policy = settings.evidence_policy(config)
        self.assertEqual(sorted(policy), sorted(settings.EVIDENCE_RETENTION_KEYS))
        self.assertTrue(all(policy.values()))

    def test_a_missing_evidence_block_defaults_to_full_retention(self):
        from chronoseal import settings
        self.assertEqual(settings.evidence_policy({}),
                         {key: True for key in settings.EVIDENCE_RETENTION_KEYS})

    def test_disabling_retention_is_rejected_with_an_actionable_message(self):
        from chronoseal import settings
        for key in settings.EVIDENCE_RETENTION_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as raised:
                    settings.evidence_policy({'evidence': {key: False}})
                message = str(raised.exception)
                self.assertIn(f'config.evidence.{key}', message)
                self.assertIn('verifiable offline', message)

    def test_a_non_object_evidence_block_is_rejected(self):
        from chronoseal import settings
        with self.assertRaises(ValueError):
            settings.evidence_policy({'evidence': ['keep_tsr']})

    def test_preflight_blocks_a_retention_opt_out(self):
        from chronoseal.pipeline import Pipeline
        pipeline = Pipeline(ROOT, {'evidence': {'keep_tsr': False}})
        with tempfile.TemporaryDirectory() as base:
            issues = pipeline.preflight(Path(base))[1]
        self.assertTrue([issue for issue in issues if 'keep_tsr' in issue],
                        f'a retention opt-out must block the run, got {issues}')


class TrustedListParserTests(unittest.TestCase):
    """The Trusted List parser is fed remote XML; it must never expand entities."""

    _XXE = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE r [<!ENTITY x SYSTEM "file:///C:/Windows/win.ini">]>\n'
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">'
        '<Name>&x;</Name></TrustServiceStatusList>\n'
    )
    _LAUGH = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>\n'
        '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#">'
        '<Name>&b;</Name></TrustServiceStatusList>\n'
    )

    def _read(self, payload):
        from chronoseal import trusted_lists
        with tempfile.TemporaryDirectory() as base:
            path = Path(base) / 'tsl.xml'
            path.write_text(payload, encoding='utf-8')
            return trusted_lists._read_xml(path)

    def test_an_external_entity_never_reaches_the_file_system(self):
        with self.assertRaises(ValueError) as raised:
            self._read(self._XXE)
        self.assertIn('document type declaration', str(raised.exception))

    def test_an_entity_expansion_bomb_is_rejected_before_parsing(self):
        with self.assertRaises(ValueError):
            self._read(self._LAUGH)

    def test_a_plain_trusted_list_root_is_still_accepted(self):
        _, root = self._read(
            '<?xml version="1.0"?>'
            '<TrustServiceStatusList xmlns="http://uri.etsi.org/02231/v2#"/>\n')
        self.assertTrue(root.tag.endswith('TrustServiceStatusList'))


class StyleLoadingResilienceTests(unittest.TestCase):
    """A denied realpath must not take down every consumer of the style rules."""

    def test_rules_load_when_realpath_is_denied(self):
        from hash_report_generator import style_loader
        original = pathlib.Path.resolve

        def denied(self, *args, **kwargs):
            if self.name == 'style' and self.parent.name == 'hash_report_generator':
                raise PermissionError(5, 'Access is denied', str(self))
            return original(self, *args, **kwargs)

        with patch.object(pathlib.Path, 'resolve', denied):
            styles = style_loader.load_styles()
        self.assertIn('PAGE', styles)
        self.assertIn('PAGE_IDENTITY', styles)

    def test_rule_outside_the_style_directory_is_rejected(self):
        from hash_report_generator.js_rules import read_js_rules
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / 'style').mkdir()
            (base / 'style' / '00_page.js').write_text('module.exports = {};', encoding='utf-8')
            outside = base / 'elsewhere.js'
            outside.write_text('module.exports = {};', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_js_rules(base / 'style', [outside])


class AppendixTitleCacheTests(unittest.TestCase):
    """A transient style-load failure must not disable appendix detection forever."""

    def setUp(self):
        from chronoseal import report_quality
        self.report_quality = report_quality
        self._saved = report_quality._APPENDIX_TITLES
        report_quality._APPENDIX_TITLES = None

    def tearDown(self):
        self.report_quality._APPENDIX_TITLES = self._saved

    def test_transient_failure_is_retried(self):
        from hash_report_generator import style_loader
        original = style_loader.load_styles
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError('node temporarily unavailable')
            return original(*args, **kwargs)

        with patch.object(style_loader, 'load_styles', flaky):
            self.assertEqual(self.report_quality._appendix_titles(), ())
            titles = self.report_quality._appendix_titles()
        self.assertIn('WHOLE FILE TEXT CHECKSUMS', titles)
        self.assertEqual(len(calls), 2)


class AtomicJsonRetryTests(unittest.TestCase):
    def test_transient_replace_failure_is_retried(self):
        from chronoseal import util
        real_replace = os.replace
        calls = []

        def flaky(source, destination):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError(13, 'file is temporarily locked')
            return real_replace(source, destination)

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'manifest.json'
            with patch.object(util.os, 'replace', flaky):
                util.atomic_json(target, {'status': 'PASS'})
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['status'], 'PASS')
        self.assertEqual(len(calls), 2)


class JsonSafeNormalisationTests(unittest.TestCase):
    """Evidence manifests must survive json.dumps even with Path members."""

    def test_path_keys_and_values_become_text(self):
        from chronoseal import util
        payload = {Path(r'C:/ev/a.txt'): Path(r'C:/ev/a.txt')}
        safe = util.json_safe(payload)
        self.assertEqual(safe, {'C:\\ev\\a.txt': 'C:\\ev\\a.txt'})
        json.dumps(safe)

    def test_nested_containers_are_normalised(self):
        from chronoseal import util
        payload = {
            'selection_paths': {Path('one.txt'): 'one.txt'},
            'roots': [Path('a'), {'deep': (Path('b'), {Path('c')})}],
            'frozen': {'x', 'y'},
            'plain': {'k': 1, 'v': None, 'ok': True},
        }
        safe = util.json_safe(payload)
        self.assertEqual(sorted(safe['selection_paths']), ['one.txt'])
        self.assertEqual(safe['roots'][0], 'a')
        self.assertEqual(safe['roots'][1]['deep'][0], 'b')
        self.assertEqual(sorted(safe['frozen']), ['x', 'y'])
        self.assertEqual(safe['plain'], {'k': 1, 'v': None, 'ok': True})
        json.dumps(safe)

    def test_json_ready_payload_is_returned_equivalent(self):
        from chronoseal import util
        payload = {'status': 'PASS', 'count': 3, 'ratio': 0.5, 'none': None}
        self.assertEqual(util.json_safe(payload), payload)


class DiscoveryPolicyWiringTests(unittest.TestCase):

    """The operator's discovery policy must reach the stand-alone generator."""

    def test_generator_environment_carries_discovery_policy(self):
        from chronoseal.pipeline import Pipeline
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / 'input'
            target.mkdir()
            (target / 'evidence.txt').write_text('x', encoding='utf-8')
            case = root / 'case'
            case.mkdir()
            script = root / 'hash_report_combined.py'
            script.write_text(
                'import json,os,sys\n'
                'from pathlib import Path\n'
                'Path(__file__).with_name("env.json").write_text(json.dumps('
                '{k:v for k,v in os.environ.items() if k.startswith("CHRONOSEAL_")}))\n'
                'Path(sys.argv[1], "RPT-20260101-000000000-ABCDEF12_HASHREPORT_TYP_COMBO.pdf")'
                '.write_bytes(b"%PDF-1.7\\n")\n',
                encoding='utf-8')
            cfg = {'generator': {'allow_unreadable_files': True, 'follow_links': True,
                                 'idle_timeout_seconds': 10}}
            pipeline = Pipeline(root, cfg, log=lambda line: None)
            pipeline._case_dir = case
            report = pipeline.generate(target, 'combined')
            env = json.loads((root / 'env.json').read_text(encoding='utf-8'))
        self.assertEqual(Path(report).name, 'RPT-20260101-000000000-ABCDEF12_HASHREPORT_TYP_COMBO.pdf')
        self.assertEqual(env['CHRONOSEAL_ALLOW_UNREADABLE_FILES'], '1')
        self.assertEqual(env['CHRONOSEAL_FOLLOW_LINKS'], '1')
        self.assertEqual(Path(env['CHRONOSEAL_EVIDENCE_DIR']), case)

    def test_preflight_warns_about_linked_entries(self):
        from chronoseal.pipeline import Pipeline
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / 'input'
            target.mkdir()
            (root / 'hash_report_combined.py').write_text('', encoding='utf-8')
            try:
                os.symlink(root, target / 'linked')
            except (OSError, NotImplementedError) as exc:
                self.skipTest('symlinks are not permitted: ' + str(exc))
            _, _, warnings = Pipeline(root, {}).preflight(target, 'combined')
        self.assertTrue(any('not be followed' in w for w in warnings), warnings)


class PythonRepairPolicyTests(unittest.TestCase):
    def test_python_install_requires_network_consent(self):
        from chronoseal import startup
        with patch.object(startup.importlib.util, 'find_spec', return_value=None), \
                patch.object(startup, '_run', return_value=(0, '')) as run:
            report = startup.ensure_python_dependencies(Path('.'), True, lambda line: None,
                                                        allow_network=False)
        self.assertTrue(report['blockers'])
        run.assert_not_called()


class CliRootDefaultTests(unittest.TestCase):
    def test_default_root_is_the_installation_directory(self):
        import chronoseal_cli
        args = chronoseal_cli.parse(['report.pdf'])
        self.assertEqual(Path(args.root).resolve(), Path(chronoseal_cli.BASE).resolve())


class GeneratorDiscoveryTests(unittest.TestCase):
    def test_discovery_skips_dependencies_and_is_deterministic(self):
        from chronoseal.pipeline import Pipeline
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'node_modules').mkdir()
            (root / 'node_modules' / 'hash_report_combined.py').write_text('', encoding='utf-8')
            expected = root / 'bundle' / 'hash_report_combined.py'
            expected.parent.mkdir()
            expected.write_text('', encoding='utf-8')
            found = Pipeline(root, {}).discover_generator(root / 'input.pdf', 'combined')
        self.assertEqual(found, expected)


if __name__ == '__main__':
    unittest.main()
