import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chronoseal.qualified_validation import validate_qualified_timestamp


class QualifiedValidationTests(unittest.TestCase):
    def setup_case(self, temporary):
        root = Path(temporary)
        config = {
            "tools": {"openssl": "openssl"},
            "rfc3161": {
                "trusted_list_validation": {
                    "lotl_file": "trust\\lotl.xml",
                    "lotl_signer_certificate_file": "trust\\lotl-signer.pem",
                    "lotl_signer_sha256": "1" * 64,
                    "member_tsl_file": "trust\\BG.xml",
                    "member_tsl_url": "https://example.invalid/BG.xml",
                },
            },
        }
        provider = {
            "name": "B-Trust-QTSA",
            "qualified": True,
            "trusted_list_service_status": "granted",
            "auth": "none",
            "service_access_confirmed": True,
            "trusted_list_service_name": "B-Trust QTSA",
            "trusted_list_service_certificate_sha256": "2" * 64,
            "trusted_list_service_certificate_file": "trust\\service.pem",
            "trust_root_files": ["trust\\root.pem"],
        }
        return root, config, provider

    def patches(self, *, chain="GOOD", revocation="GOOD", signer="2" * 64, path=("2" * 64,)):
        return (
            patch(
                "chronoseal.qualified_validation.verify_lotl_and_member_tsl",
                return_value={"status": "PASS"},
            ),
            patch(
                "chronoseal.qualified_validation.verify_qualified_tsa_service_status",
                return_value={"status": "GRANTED", "identity_sha256": "2" * 64},
            ),
            patch(
                "chronoseal.qualified_validation.validate_rfc3161_token",
                return_value={
                    "signer_sha256": signer,
                    "certificate_path_sha256": list(path),
                    "root_sha256": "3" * 64,
                    "root_trust_status": "PASS (explicitly configured trust root)",
                    "chain": {"status": chain, "detail": "test"},
                    "crl": {"status": revocation},
                    "ocsp": {"status": "UNAVAILABLE"},
                    "artifacts": [{"filename": "test.crl", "kind": "CRL", "data": b"evidence"}],
                },
            ),
        )

    def test_unprovisioned_trusted_lists_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, config, provider = self.setup_case(temporary)
            config["rfc3161"]["trusted_list_validation"]["lotl_signer_sha256"] = ""
            with self.assertRaisesRegex(ValueError, "missing Trusted List fields"):
                validate_qualified_timestamp(
                    token_der=b"token",
                    gen_time="2026-10-09T04:00:00Z",
                    config=config,
                    provider=provider,
                    project_root=root,
                    evidence_dir=root / "evidence",
                )

    def test_good_chain_and_authenticated_revocation_evidence_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, config, provider = self.setup_case(temporary)
            contexts = [patcher.start() for patcher in self.patches()]
            self.addCleanup(lambda: [context.stop() for context in contexts])
            result = validate_qualified_timestamp(
                token_der=b"token",
                gen_time="2026-10-09T04:00:00Z",
                config=config,
                provider=provider,
                project_root=root,
                evidence_dir=root / "evidence",
            )
            self.assertEqual(result["status"], "PASS")
            self.assertTrue((root / "evidence" / "test.crl").is_file())

    def test_bad_chain_or_missing_good_revocation_evidence_blocks(self):
        for chain, revocation, error in (
            ("FAILED", "GOOD", "chain did not validate"),
            ("GOOD", "UNAVAILABLE", "No authenticated, fresh"),
        ):
            with self.subTest(chain=chain, revocation=revocation), tempfile.TemporaryDirectory() as temporary:
                root, config, provider = self.setup_case(temporary)
                contexts = [patcher.start() for patcher in self.patches(chain=chain, revocation=revocation)]
                try:
                    with self.assertRaisesRegex(ValueError, error):
                        validate_qualified_timestamp(
                            token_der=b"token",
                            gen_time="2026-10-09T04:00:00Z",
                            config=config,
                            provider=provider,
                            project_root=root,
                            evidence_dir=root / "evidence",
                        )
                finally:
                    for context in contexts:
                        context.stop()

    def test_tsl_issuing_ca_may_appear_above_the_timestamp_signer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, config, provider = self.setup_case(temporary)
            contexts = [
                patcher.start()
                for patcher in self.patches(signer="4" * 64, path=("4" * 64, "2" * 64, "3" * 64))
            ]
            try:
                result = validate_qualified_timestamp(
                    token_der=b"token",
                    gen_time="2026-10-09T04:00:00Z",
                    config=config,
                    provider=provider,
                    project_root=root,
                    evidence_dir=root / "evidence",
                )
                self.assertEqual(result["status"], "PASS")
            finally:
                for context in contexts:
                    context.stop()

    def test_tsl_identity_must_be_in_the_validated_signer_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, config, provider = self.setup_case(temporary)
            contexts = [
                patcher.start()
                for patcher in self.patches(signer="4" * 64, path=("4" * 64, "3" * 64))
            ]
            try:
                with self.assertRaisesRegex(ValueError, "does not contain the qualified TSL service identity"):
                    validate_qualified_timestamp(
                        token_der=b"token",
                        gen_time="2026-10-09T04:00:00Z",
                        config=config,
                        provider=provider,
                        project_root=root,
                        evidence_dir=root / "evidence",
                    )
            finally:
                for context in contexts:
                    context.stop()


if __name__ == "__main__":
    unittest.main()
