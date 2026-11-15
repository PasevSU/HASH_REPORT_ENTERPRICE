import threading, unittest
import ChronoSeal_Original_Legacy as L


class LegacyThreadAffinityTest(unittest.TestCase):
    def test_worker_ui_ops_run_on_main_thread(self):
        try:
            app = L.App(auto_bootstrap=False)
        except Exception as e:
            self.skipTest(f"Tk unavailable: {e}")
        app.withdraw()
        seen = {}
        orig = app.log.insert
        def spy(*a, **k):
            seen["w"] = threading.get_ident()
            return orig(*a, **k)
        app.log.insert = spy
        def job():
            app.write("hello")
            seen["r"] = app._call_main(lambda: (threading.get_ident(), 42))
            seen["done"] = True
        th = threading.Thread(target=job); th.start()
        while th.is_alive():
            app.update(); th.join(0.01)
        app.update(); app.update()
        main = threading.get_ident()
        self.assertEqual(seen["r"], (main, 42))
        self.assertEqual(seen["w"], main)
        self.assertIn("hello", app.log.get("1.0", "end"))
        app.destroy()


if __name__ == "__main__":
    unittest.main()
