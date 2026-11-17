"""Report-name orchestrator: names, input kinds, --url and the delegation contract."""

import contextlib, io, os, sys, tempfile, unittest

from pathlib import Path

from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chronoseal_cli as cli

import chronoseal_report as report

from chronoseal import verification_qr


class FakePipeline:
    """Keeps the orchestrator tests offline; records the run arguments."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.cfg = args[1] if len(args) > 1 else {}
        self.session = None
        self.ran = None
        FakePipeline.instances.append(self)

    def run(self, target, mode='combined', recursive=False, explain=False, source_pdf=False,
            output_dir=None, filters=None, files=None, embed_pdf=None, embed_position='after',
            qr_url=''):
        self.ran = {'target': str(target), 'mode': mode, 'recursive': recursive,
                    'explain': explain, 'source_pdf': source_pdf, 'output_dir': output_dir,
                    'filters': filters, 'files': [str(item) for item in (files or [])],
                    'embed_pdf': str(embed_pdf) if embed_pdf else None,
                    'embed_position': embed_position, 'qr_url': qr_url}
        return {'final_pdf': str(Path(target) / 'REPORT_HASHREPORT_TYP_COMBO_PDF.pdf')}


class OrchestratorTests(unittest.TestCase):

    def setUp(self):
        FakePipeline.instances = []
        self._env = os.environ.get(verification_qr.BASE_URL_ENV)
        os.environ.pop(verification_qr.BASE_URL_ENV, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.file = self.dir / 'report.pdf'
        self.file.write_bytes(b'%PDF-1.4\n')
        self.folder = self.dir / 'in'
        self.folder.mkdir()

    def tearDown(self):
        self.tmp.cleanup()
        if self._env is None:
            os.environ.pop(verification_qr.BASE_URL_ENV, None)
        else:
            os.environ[verification_qr.BASE_URL_ENV] = self._env

    def run_report(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli, 'Pipeline', FakePipeline), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = report.main(argv + ['--log-dir', str(self.dir / 'logs')])
        return code, out.getvalue(), err.getvalue()

    def last_run(self):
        self.assertTrue(FakePipeline.instances, 'the pipeline was never called')
        return FakePipeline.instances[-1]

    def test_list_names_every_report_and_explains_the_redirect(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report.main(['list'])
        text = out.getvalue()
        self.assertEqual(code, 0)
        for name in ('SINGLE', 'SINGLE_PDF', 'COMBO', 'COMBO_PDF', 'COMBO_ALL', 'COMBO_ALL_PDF'):
            with self.subTest(name=name):
                self.assertIn(name, text)
        self.assertIn('redirect', text)
        self.assertIn('TWO documents', text)

    def test_information_does_not_run_the_pipeline(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = report.main(['--information'])
        self.assertEqual(code, 0)
        self.assertIn('package for adaptation', out.getvalue())
        self.assertEqual(FakePipeline.instances, [])

    def test_single_names_the_file_and_the_single_mode(self):
        code, out, err = self.run_report(['single', str(self.file)])
        self.assertEqual(code, 0, err)
        ran = self.last_run().ran
        self.assertEqual(ran['mode'], 'single')
        self.assertEqual(Path(ran['target']), self.file)
        self.assertFalse(ran['source_pdf'])
        self.assertIsNone(ran['embed_pdf'])

    def test_single_pdf_embeds_the_input_byte_exact(self):
        code, out, err = self.run_report(['SINGLE_PDF', str(self.file)])
        self.assertEqual(code, 0, err)
        ran = self.last_run().ran
        self.assertEqual(ran['mode'], 'single')
        self.assertTrue(ran['source_pdf'])

    def test_combo_all_walks_subfolders(self):
        code, out, err = self.run_report(['COMBO_ALL', str(self.folder)])
        self.assertEqual(code, 0, err)
        ran = self.last_run().ran
        self.assertEqual(ran['mode'], 'combined')
        self.assertTrue(ran['recursive'])

    def test_combo_does_not_walk_subfolders(self):
        code, out, err = self.run_report(['COMBO', str(self.folder)])
        self.assertEqual(code, 0, err)
        self.assertFalse(self.last_run().ran['recursive'])

    def test_pdf_reports_forward_the_embedded_pdf_and_its_position(self):
        pdf = self.dir / 'cover.pdf'
        pdf.write_bytes(b'%PDF-1.4\n')
        code, out, err = self.run_report(['COMBO_ALL_PDF', str(self.folder), '--pdf', str(pdf),
                                          '--position', 'before'])
        self.assertEqual(code, 0, err)
        ran = self.last_run().ran
        self.assertEqual(ran['mode'], 'combined')
        self.assertTrue(ran['recursive'])
        self.assertEqual(Path(ran['embed_pdf']), pdf)
        self.assertEqual(ran['embed_position'], 'before')

    def test_pdf_report_without_the_pdf_is_blocked(self):
        code, out, err = self.run_report(['COMBO_PDF', str(self.folder)])
        self.assertEqual(code, 2)
        self.assertIn('BLOCKED', err)
        self.assertIn('--pdf', err)
        self.assertEqual(FakePipeline.instances, [])

    def test_missing_embedded_pdf_is_blocked(self):
        code, out, err = self.run_report(['COMBO_PDF', str(self.folder),
                                          '--pdf', str(self.dir / 'nope.pdf')])
        self.assertEqual(code, 2)
        self.assertIn('not found', err)

    def test_plain_report_refuses_a_second_pdf(self):
        pdf = self.dir / 'cover.pdf'
        pdf.write_bytes(b'%PDF-1.4\n')
        code, out, err = self.run_report(['SINGLE', str(self.file), '--pdf', str(pdf)])
        self.assertEqual(code, 2)
        self.assertIn('SINGLE_PDF', err)

    def test_report_name_and_input_kind_must_match(self):
        for argv in (['COMBO', str(self.file)], ['SINGLE', str(self.folder)]):
            with self.subTest(argv=argv):
                code, out, err = self.run_report(argv)
                self.assertEqual(code, 2)
                self.assertIn('needs an existing', err)

    def test_combo_accepts_an_explicit_file_set(self):
        second = self.dir / 'sub'
        second.mkdir()
        other = second / 'second.pdf'
        other.write_bytes(b'%PDF-1.4\n')
        code, out, err = self.run_report(['COMBO', '--file', str(self.file), '--file', str(other)])
        self.assertEqual(code, 0, err)
        ran = self.last_run().ran
        self.assertEqual(ran['mode'], 'combined')
        self.assertEqual([Path(item) for item in ran['files']], [self.file, other])
        self.assertEqual(Path(ran['target']), self.dir)

    def test_explicit_file_set_rejects_a_filter_chain(self):
        code, out, err = self.run_report(['COMBO', '--file', str(self.file), '--filter', '*.pdf'])
        self.assertEqual(code, 2)
        self.assertIn('cannot be combined', out + err)
        self.assertEqual(FakePipeline.instances, [])

    def test_explicit_file_set_rejects_a_recursive_report(self):
        code, out, err = self.run_report(['COMBO_ALL', '--file', str(self.file)])
        self.assertEqual(code, 2)
        self.assertIn('COMBO', out + err)

    def test_missing_selected_file_is_blocked(self):
        code, out, err = self.run_report(['COMBO', '--file', str(self.dir / 'gone.pdf')])
        self.assertEqual(code, 2)
        self.assertIn('not found', out + err)

    def test_filters_are_chained_on_a_folder_report(self):
        code, out, err = self.run_report(['COMBO', str(self.folder),
                                          '--filter', '*.eml', '--filter', '*.pdf'])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_run().ran['filters'], ['*.eml', '*.pdf'])

    def test_filters_are_refused_for_a_single_file_report(self):
        code, out, err = self.run_report(['SINGLE', str(self.file), '--filter', '*.pdf'])
        self.assertEqual(code, 2)
        self.assertIn('only apply to a folder report', out + err)

    def test_a_report_without_an_input_is_blocked(self):
        code, out, err = self.run_report(['COMBO'])
        self.assertEqual(code, 2)
        self.assertIn('needs a folder', out + err)
        self.assertEqual(FakePipeline.instances, [])

    def test_unknown_report_lists_the_known_names(self):
        code, out, err = self.run_report(['NOPE', str(self.file)])
        self.assertEqual(code, 2)
        self.assertIn('unknown report', err)
        self.assertIn('COMBO_ALL_PDF', err)

    def test_url_sets_the_evidence_host_of_the_run(self):
        code, out, err = self.run_report(['SINGLE', str(self.file), '--url', 'https://example.net/static'])
        self.assertEqual(code, 0, err)
        pipeline = self.last_run()
        self.assertEqual(pipeline.cfg['verification']['base_url'], 'https://example.net/static/')
        self.assertIn('https://example.net/static/', out)
        link = verification_qr.new_link(pipeline.cfg, environ={})
        self.assertTrue(link['url'].startswith('https://example.net/static/'))
        self.assertEqual(len(link['code'].replace('-', '')), 37)
        self.assertTrue(link['url'].endswith(link['code']))

    def test_url_replaces_a_configured_host(self):
        code, out, err = self.run_report(['SINGLE', str(self.file), '--url', 'https://other.example/x/'])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_run().cfg['verification']['base_url'], 'https://other.example/x/')

    def test_url_outranks_the_environment_variable(self):
        os.environ[verification_qr.BASE_URL_ENV] = 'https://from-env.example/env/'
        code, out, err = self.run_report(['SINGLE', str(self.file), '--url', 'https://from-flag.example/f/'])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_run().cfg['verification']['base_url'], 'https://from-flag.example/f/')
        options = verification_qr.resolve(self.last_run().cfg, environ={})
        self.assertTrue(options['url'].startswith('https://from-flag.example/f/'))

    def test_relative_url_is_blocked(self):
        code, out, err = self.run_report(['SINGLE', str(self.file), '--url', 'ftp://example.net/'])
        self.assertEqual(code, 2)
        self.assertIn('http://', out + err)
        self.assertEqual(FakePipeline.instances, [])

    def test_report_without_url_keeps_the_configured_base(self):
        code, out, err = self.run_report(['SINGLE', str(self.file)])
        self.assertEqual(code, 0, err)
        self.assertIn('base_url', self.last_run().cfg.get('verification', {}))


if __name__ == '__main__':
    unittest.main()
