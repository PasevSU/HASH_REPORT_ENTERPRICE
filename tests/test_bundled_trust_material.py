import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BundledTrustMaterialTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (ROOT / "config" / "config.json").read_text(encoding="utf-8")
        )
        self.openssl = (
            self.config.get("tools", {}).get("openssl")
            if Path(self.config.get("tools", {}).get("openssl", "")).is_file()
            else shutil.which("openssl")
        )

    def test_all_configured_trust_paths_are_portable_and_present(self):
        self.assertTrue(self.openssl, "OpenSSL is required for configured trust validation")
        policy = self.config["rfc3161"]
        for stage in ("start", "stop"):
            for provider in policy[stage]:
                for key in (
                    "trust_root_files",
                    "intermediate_certificate_files",
                    "embed_certificate_files",
                ):
                    for configured in provider.get(key, []):
                        path = Path(configured)
                        self.assertFalse(path.is_absolute(), configured)
                        resolved = (ROOT / path).resolve()
                        self.assertTrue(resolved.is_file(), str(resolved))
                        result = subprocess.run(
                            [self.openssl, "x509", "-in", str(resolved), "-noout", "-subject"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bundled_tsa_chains_verify_to_configured_roots(self):
        self.assertTrue(self.openssl, "OpenSSL is required for configured trust validation")
        cases = (
            (
                "trust\\FreeTSA\\certificate-2.pem",
                "trust\\FreeTSA\\certificate-1.pem",
                "trust\\FreeTSA\\certificate-1.pem",
            ),
            (
                "trust\\DigiCert\\chain-3.pem",
                "trust\\DigiCert\\chain-2.pem",
                "trust\\DigiCert\\chain-1.pem",
            ),
        )
        for root, intermediate, signer in cases:
            with self.subTest(signer=signer):
                result = subprocess.run(
                    [
                        self.openssl,
                        "verify",
                        "-purpose",
                        "timestampsign",
                        "-CAfile",
                        str(ROOT / root),
                        "-untrusted",
                        str(ROOT / intermediate),
                        str(ROOT / signer),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
