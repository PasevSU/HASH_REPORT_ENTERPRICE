"""Progress-aware watchdog regression tests.

The generator is a black box that can legitimately run for many minutes on a
large evidence tree (40k files / 7 GB on a slow disk), so the watchdog must kill
a stalled child instead of a busy one, and must expose progress while it runs.
"""
import subprocess, sys, tempfile, time, unittest
from pathlib import Path

from chronoseal.pipeline import Pipeline, PipelineError, Cancelled


def make_pipeline(root, log=None):
    return Pipeline(root, {}, log=log or (lambda line: None))


def python(code):
    return [sys.executable, '-c', code]


class WatchdogTests(unittest.TestCase):
    def test_idle_timeout_terminates_silent_child(self):
        with tempfile.TemporaryDirectory() as td:
            p = make_pipeline(Path(td))
            started = time.monotonic()
            with self.assertRaises(PipelineError) as raised:
                p._run(python('import time; time.sleep(30)'), idle_timeout=0.5)
            self.assertLess(time.monotonic() - started, 10)
            self.assertIn('no output', str(raised.exception))

    def test_absolute_timeout_still_wins_over_activity(self):
        with tempfile.TemporaryDirectory() as td:
            p = make_pipeline(Path(td))
            with self.assertRaises(PipelineError) as raised:
                p._run(python('import time\nfor _ in range(200):\n print("tick", flush=True)\n time.sleep(0.05)'),
                       timeout=0.6, idle_timeout=30)
            self.assertIn('total runtime', str(raised.exception))

    def test_chatty_child_survives_idle_timeout(self):
        # Output resets the idle budget: this child runs longer than the idle
        # window but keeps making progress, so it must not be killed.
        with tempfile.TemporaryDirectory() as td:
            p = make_pipeline(Path(td))
            code = 'import time\nfor _ in range(6):\n print("working", flush=True)\n time.sleep(0.25)'
            done = p._run(python(code), idle_timeout=1.0)
            self.assertEqual(done.returncode, 0)

    def test_progress_is_streamed_before_the_child_exits(self):
        # The line must reach the log while the child is still alive; otherwise a
        # long generation looks like a hang for its whole duration.
        with tempfile.TemporaryDirectory() as td:
            lines = []
            p = make_pipeline(Path(td), log=lines.append)
            with self.assertRaises(PipelineError):
                p._run(python('import time\nprint("phase-1", flush=True)\ntime.sleep(30)'),
                       idle_timeout=0.6, stream=True)
            self.assertTrue(any('phase-1' in line for line in lines), lines)

    def test_cancel_terminates_streaming_child(self):
        import threading
        with tempfile.TemporaryDirectory() as td:
            cancel = threading.Event()
            p = Pipeline(Path(td), {}, cancel_event=cancel)
            threading.Timer(0.4, cancel.set).start()
            started = time.monotonic()
            with self.assertRaises(Cancelled):
                p._run(python('import time; time.sleep(30)'), idle_timeout=30, stream=True)
            self.assertLess(time.monotonic() - started, 10)

    def test_large_output_does_not_deadlock_the_pipes(self):
        with tempfile.TemporaryDirectory() as td:
            p = make_pipeline(Path(td))
            done = p._run(python('import sys\nfor i in range(20000): sys.stdout.write("line %d\\n" % i)'),
                          idle_timeout=60)
            self.assertEqual(done.returncode, 0)

    def test_stderr_is_reported_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p = make_pipeline(Path(td))
            with self.assertRaises(PipelineError) as raised:
                p._run(python('import sys; sys.stderr.write("boom\\n"); sys.exit(3)'), idle_timeout=30)
            self.assertIn('boom', str(raised.exception))


class GeneratorBudgetTests(unittest.TestCase):
    def test_generator_budget_reads_idle_timeout_and_allows_no_cap(self):
        import inspect
        source = inspect.getsource(Pipeline.generate)
        self.assertIn('idle_timeout_seconds', source)
        self.assertIn('stream=True', source)
        self.assertNotIn("get('timeout_seconds',180)", source)


if __name__ == '__main__':
    unittest.main()
