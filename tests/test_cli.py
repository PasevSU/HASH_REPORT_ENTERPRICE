"""Headless CLI contract: exit codes, JSON result, no GUI dependency."""

import contextlib, importlib, io, json, sys, tempfile, unittest

from pathlib import Path

from unittest.mock import patch



ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))

import chronoseal_cli as cli





class FakePipeline:

    """Stand-in that keeps the CLI tests offline and fast."""



    def __init__(self, *args, **kwargs):

        self.cfg = args[1] if len(args) > 1 else {}

        self.session = None

        self.ran = None



    def preflight(self, target, pdf_embed=False, combo_embed=False):

        self.preflighted = (pdf_embed, combo_embed)

        return {'target': str(target), 'input_kind': 'source'}, [], ['a warning']



    def run(self, target, mode='combined', recursive=False, explain=False, source_pdf=False, output_dir=None,

            filters=None, files=None, embed_pdf=None, embed_position='after', qr_url=''):
        self.ran = (target, mode, recursive, explain, source_pdf, output_dir, embed_pdf, embed_position)
        self.selection = (filters, files)
        self.qr_url = qr_url
        return {'final_pdf': str(Path(target) / 'REPORT_HASHREPORT_TYP_COMBO_PDF.pdf')}



    @property

    def embedding(self):

        return self.ran[-2:]





class CliTests(unittest.TestCase):

    def run_cli(self, argv, pipeline=FakePipeline):

        out, err = io.StringIO(), io.StringIO()

        with patch.object(cli, 'Pipeline', pipeline), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):

            code = cli.main(argv)

        return code, out.getvalue(), err.getvalue()



    def test_cli_does_not_pull_in_tkinter(self):

        # Headless hosts have no display; the CLI must never import the GUI stack.

        import subprocess

        probe = 'import sys, chronoseal_cli; sys.exit(1 if "tkinter" in sys.modules else 0)'

        done = subprocess.run([sys.executable, '-c', probe], cwd=str(ROOT), capture_output=True, text=True, timeout=120)

        self.assertEqual(done.returncode, 0, done.stderr)



    def test_missing_target_is_blocked(self):

        code, out, _ = self.run_cli(['--json'])

        self.assertEqual(code, cli.EXIT_BLOCKED)

        self.assertEqual(json.loads(out)['status'], 'BLOCKED')



    def test_preflight_json_is_clean_on_stdout(self):

        with tempfile.TemporaryDirectory() as td:

            code, out, err = self.run_cli([td, '--preflight', '--json'])

            payload = json.loads(out)

            self.assertIn('WARNING: a warning', err)

        self.assertEqual(code, cli.EXIT_PASS)

        self.assertEqual(payload['status'], 'PASS')

        self.assertEqual(payload['warnings'], ['a warning'])



    def test_run_returns_pass_and_reports_the_pdf(self):

        with tempfile.TemporaryDirectory() as td:

            code, out, _ = self.run_cli([td, '--json', '--log-dir', str(Path(td) / 'logs')])

            payload = json.loads(out)

            self.assertEqual(code, cli.EXIT_PASS)

            self.assertEqual(payload['status'], 'PASS')

            self.assertTrue(payload['final_pdf'].endswith('_HASHREPORT_TYP_COMBO_PDF.pdf'))

            self.assertTrue(Path(payload['session_dir'], 'chronoseal.log').is_file())

            self.assertTrue(Path(payload['session_dir'], 'environment.json').is_file())



    def test_embed_flags_reach_the_pipeline_verbatim(self):

        with tempfile.TemporaryDirectory() as td:

            pdf = Path(td) / 'attached.pdf'

            pdf.write_bytes(b'%PDF-1.7\n')

            holder = {}



            class Recorder(FakePipeline):

                def __init__(self, *a, **k):

                    super().__init__(*a, **k)

                    holder['pipeline'] = self



            code, _, err = self.run_cli([td, '--embed-pdf', str(pdf), '--embed-position', 'before', '--quiet',

                                         '--log-dir', str(Path(td) / 'logs')], Recorder)

            self.assertEqual(code, cli.EXIT_PASS, err)

            self.assertEqual(holder['pipeline'].embedding, (pdf, 'before'))



    def test_embed_position_defaults_to_after(self):

        with tempfile.TemporaryDirectory() as td:

            pdf = Path(td) / 'attached.pdf'

            pdf.write_bytes(b'%PDF-1.7\n')

            holder = {}



            class Recorder(FakePipeline):

                def __init__(self, *a, **k):

                    super().__init__(*a, **k)

                    holder['pipeline'] = self



            code, _, err = self.run_cli([td, '--embed-pdf', str(pdf), '--quiet',

                                         '--log-dir', str(Path(td) / 'logs')], Recorder)

            self.assertEqual(code, cli.EXIT_PASS, err)

            self.assertEqual(holder['pipeline'].embedding[1], 'after')



    def test_qr_url_reaches_the_pipeline_verbatim(self):
        with tempfile.TemporaryDirectory() as td:
            holder = {}

            class Recorder(FakePipeline):
                def __init__(self, *a, **k):
                    super().__init__(*a, **k)
                    holder['pipeline'] = self

            code, _, err = self.run_cli([td, '--qr-url', 'https://evidence.example.org/case-42/',
                                         '--quiet', '--log-dir', str(Path(td) / 'logs')], Recorder)
            self.assertEqual(code, cli.EXIT_PASS, err)
            self.assertEqual(holder['pipeline'].qr_url, 'https://evidence.example.org/case-42/')

    def test_the_closing_qr_block_needs_no_flag(self):
        # The block is mandatory, so the pipeline is asked to generate the link: the
        # CLI passes no override and never asks for the block to be left out.
        with tempfile.TemporaryDirectory() as td:
            holder = {}

            class Recorder(FakePipeline):
                def __init__(self, *a, **k):
                    super().__init__(*a, **k)
                    holder['pipeline'] = self

            code, _, err = self.run_cli([td, '--quiet', '--log-dir', str(Path(td) / 'logs')], Recorder)
            self.assertEqual(code, cli.EXIT_PASS, err)
            self.assertEqual(holder['pipeline'].qr_url, '')

    def test_preflight_reports_both_embedding_routes(self):

        with tempfile.TemporaryDirectory() as td:

            pdf = Path(td) / 'attached.pdf'

            pdf.write_bytes(b'%PDF-1.7\n')

            holder = {}



            class Recorder(FakePipeline):

                def __init__(self, *a, **k):

                    super().__init__(*a, **k)

                    holder['pipeline'] = self



            code, _, err = self.run_cli([td, '--preflight', '--source-pdf', '--embed-pdf', str(pdf), '--quiet'],

                                         Recorder)

            self.assertEqual(code, cli.EXIT_PASS, err)

            self.assertEqual(holder['pipeline'].preflighted, (True, True))



    def test_pipeline_error_maps_to_blocked_and_records_traceback(self):

        class Broken(FakePipeline):

            def run(self, *a, **k):

                raise cli.PipelineError('PRE-FLIGHT BLOCKED: no trust')

        with tempfile.TemporaryDirectory() as td:

            code, out, _ = self.run_cli([td, '--json', '--log-dir', str(Path(td) / 'logs')], Broken)

            payload = json.loads(out)

            self.assertEqual(code, cli.EXIT_BLOCKED)

            self.assertEqual(payload['status'], 'BLOCKED')

            self.assertIn('no trust', payload['error'])

            self.assertTrue(Path(payload['session_dir'], 'error.txt').is_file())



    def test_cancel_maps_to_exit_130(self):

        class Cancelled(FakePipeline):

            def run(self, *a, **k):

                raise cli.Cancelled('Operation cancelled by user.')

        with tempfile.TemporaryDirectory() as td:

            code, out, _ = self.run_cli([td, '--json', '--log-dir', str(Path(td) / 'logs')], Cancelled)

        self.assertEqual(code, cli.EXIT_CANCELLED)

        self.assertEqual(json.loads(out)['status'], 'CANCELLED')



    def test_legacy_flags_are_still_accepted(self):

        # The old positional interface must keep working for existing scripts.

        with tempfile.TemporaryDirectory() as td:

            code, _, _ = self.run_cli([td, '--mode', 'single', '--recursive', '--quiet', '--log-dir', str(Path(td) / 'logs')])

        self.assertEqual(code, cli.EXIT_PASS)





if __name__ == '__main__':

    unittest.main()

