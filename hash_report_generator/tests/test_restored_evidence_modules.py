import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509 import ocsp
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    ExtendedKeyUsageOID,
    NameOID,
)

from hash_report_generator import evidence_database, rfc3161_validation

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from chronoseal.settings import executable


def _certificate(subject, issuer, public_key, signer_key, *, ca, eku=None,
                 key_usage=None, crl_uri=None, ocsp_uri=None):
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.subject if isinstance(issuer, x509.Certificate) else issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
    )
    if isinstance(issuer, x509.Certificate):
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.public_key()),
            critical=False,
        )
    if eku is not None:
        builder = builder.add_extension(x509.ExtendedKeyUsage(eku), critical=True)
    if key_usage is not None:
        builder = builder.add_extension(key_usage, critical=True)
    if crl_uri:
        builder = builder.add_extension(
            x509.CRLDistributionPoints([x509.DistributionPoint(
                full_name=[x509.UniformResourceIdentifier(crl_uri)],
                relative_name=None,
                reasons=None,
                crl_issuer=None,
            )]),
            critical=False,
        )
    if ocsp_uri:
        builder = builder.add_extension(
            x509.AuthorityInformationAccess([x509.AccessDescription(
                AuthorityInformationAccessOID.OCSP,
                x509.UniformResourceIdentifier(ocsp_uri),
            )]),
            critical=False,
        )
    return builder.sign(signer_key, hashes.SHA256())


def _crl(cert, issuer, signing_key, *, now, revoked_at=None, next_update=None):
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer.subject)
        .last_update(now - timedelta(hours=1))
        .next_update(next_update or now + timedelta(hours=1))
    )
    if revoked_at is not None:
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(cert.serial_number)
            .revocation_date(revoked_at)
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)
    return builder.sign(signing_key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


def _ocsp_response(cert, issuer, signing_key, *, now, status, revoked_at=None,
                   responder=None, responder_key=None, include_responder=False,
                   this_update=None, next_update=None):
    builder = (
        ocsp.OCSPResponseBuilder()
        .add_response(
            cert=cert,
            issuer=issuer,
            algorithm=hashes.SHA1(),
            cert_status=status,
            this_update=this_update or now - timedelta(hours=1),
            next_update=next_update or now + timedelta(hours=1),
            revocation_time=revoked_at,
            revocation_reason=None,
        )
    )
    responder = responder or issuer
    responder_key = responder_key or signing_key
    builder = builder.responder_id(ocsp.OCSPResponderEncoding.HASH, responder)
    if include_responder:
        builder = builder.certificates([responder])
    return builder.sign(responder_key, hashes.SHA256()).public_bytes(serialization.Encoding.DER)


class RestoredEvidenceModulesTests(unittest.TestCase):
    def test_sqlite_record_stores_report_files_and_binary_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF-1.4\nreport\n")
            artifact_data = b"timestamp-response-der"
            source = root / "input.bin"
            source.write_bytes(b"evidence")
            generator = SimpleNamespace(
                system_info={"os": "test"},
                user_info={"user": "tester"},
                _rfc3161_validation_artifacts={
                    "START": [{
                        "filename": "RFC3161_START_CERT.pem",
                        "kind": "X509_CERTIFICATE",
                        "data": artifact_data,
                    }]
                },
                _rfc3161_responses={"START": b"raw-tsr"},
            )
            record = evidence_database.build_record(
                generator,
                report_id="RPT-TEST",
                report_type="SINGLE",
                generated_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
                timezone_label="UTC",
                output_pdf=pdf,
                files_info=[{
                    "path": str(source), "name": source.name,
                    "size": source.stat().st_size,
                    "hash": hashlib.sha256(source.read_bytes()).hexdigest(),
                }],
                evidence_sha256="a" * 64,
                start_timestamp_text="START",
                end_timestamp_text="STOP",
                end_message_imprint="b" * 64,
                start_anchor_type="SHA-256",
                processing_duration_ms=25.5,
                embedded_pdf_artifacts=[],
            )
            saved = evidence_database.save_record(root / "evidence.sqlite3", record)
            self.assertEqual(saved["artifact_count"], 2)
            db = sqlite3.connect(saved["path"])
            try:
                self.assertEqual(db.execute("SELECT report_id FROM reports").fetchone()[0], "RPT-TEST")
                self.assertEqual(db.execute("SELECT count(*) FROM report_files").fetchone()[0], 1)
                artifacts = db.execute("SELECT filename, data FROM report_artifacts ORDER BY ordinal").fetchall()
                self.assertEqual(len(artifacts), 2)
                self.assertEqual(artifacts[0][1], artifact_data)
                self.assertEqual(artifacts[1][1], b"raw-tsr")
            finally:
                db.close()

    def test_invalid_file_digest_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            with self.assertRaisesRegex(ValueError, "valid SHA-256"):
                evidence_database.build_record(
                    SimpleNamespace(system_info={}, user_info={}),
                    report_id="RPT-INVALID",
                    report_type="SINGLE",
                    generated_at=datetime.now(timezone.utc),
                    timezone_label="UTC",
                    output_pdf=pdf,
                    files_info=[{"name": "bad.bin", "hash": "not-a-digest"}],
                    evidence_sha256="a" * 64,
                    start_timestamp_text="",
                    end_timestamp_text="",
                    end_message_imprint="",
                    start_anchor_type="",
                    processing_duration_ms=0,
                    embedded_pdf_artifacts=[],
                )

    def test_signer_eku_and_embedded_certificate_are_validated(self):
        # Use the product resolver: OpenSSL is often installed but absent from PATH.
        openssl = executable("openssl")
        if not openssl:
            self.skipTest("OpenSSL executable is required for CMS signer extraction")
        root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA Root")])
        root = _certificate(root_name, root_name, root_key.public_key(), root_key, ca=True)
        signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA Signer")])
        signer = _certificate(
            signer_name, root, signer_key.public_key(), root_key, ca=False,
            eku=[ExtendedKeyUsageOID.TIME_STAMPING],
        )
        token = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"synthetic timestamp content")
            .add_signer(signer, signer_key, hashes.SHA256())
            .add_certificate(root)
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.Binary],
            )
        )

        now = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as directory:
            root_path = Path(directory) / "tsa-root.pem"
            root_path.write_bytes(root.public_bytes(serialization.Encoding.PEM))
            with patch.dict(os.environ, {
                "CHRONOSEAL_TSA_TRUST_ROOTS": json.dumps([str(root_path)]),
                "CHRONOSEAL_TSA_INTERMEDIATES": "[]",
            }):
                result = rfc3161_validation.validate_rfc3161_token(
                    token_der=token,
                    marker="START",
                    openssl_path=openssl,
                    gen_time_text=now,
                )
        self.assertEqual(result["signer_subject"], signer.subject.rfc4514_string())
        self.assertIn("TSA Signer EKU Time Stamping: PASS", " ".join(result["lines"]))
        self.assertEqual(result["chain"]["status"], "GOOD")
        self.assertIn("explicitly configured trust root", result["root_trust_status"])
        self.assertEqual(result["root_sha256"], root.fingerprint(hashes.SHA256()).hex())
        self.assertEqual(result["crl"]["status"], "UNAVAILABLE")
        self.assertEqual(result["ocsp"]["status"], "UNAVAILABLE")
        self.assertEqual(len(result["artifacts"]), 3)

    def test_missing_timestamp_eku_fails_closed(self):
        openssl = executable("openssl")
        if not openssl:
            self.skipTest("OpenSSL executable is required for CMS signer extraction")
        root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test TSA Root")])
        root = _certificate(root_name, root_name, root_key.public_key(), root_key, ca=True)
        signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Not a TSA")])
        signer = _certificate(signer_name, root, signer_key.public_key(), root_key, ca=False)
        token = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"synthetic timestamp content")
            .add_signer(signer, signer_key, hashes.SHA256())
            .add_certificate(root)
            .sign(
                serialization.Encoding.DER,
                [pkcs7.PKCS7Options.Binary],
            )
        )

        def fake_openssl(_openssl, args, *, timeout=30):
            if "-signer" in args:
                Path(args[args.index("-signer") + 1]).write_bytes(signer.public_bytes(serialization.Encoding.PEM))
            return SimpleNamespace(stdout="synthetic OpenSSL verification\n", stderr="")

        with patch.object(rfc3161_validation, "_run_openssl", side_effect=fake_openssl):
            with self.assertRaisesRegex(ValueError, "lacks Extended Key Usage"):
                rfc3161_validation.validate_rfc3161_token(
                    token_der=token,
                    marker="START",
                    openssl_path=openssl,
                    gen_time_text=datetime.now(timezone.utc).isoformat(),
                )

    def test_crl_signature_freshness_and_revocation_status(self):
        now = datetime.now(timezone.utc)
        root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CRL Test Root")])
        root = _certificate(root_name, root_name, root_key.public_key(), root_key, ca=True)
        signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CRL Test Signer")])
        signer = _certificate(
            signer_name, root, signer_key.public_key(), root_key, ca=False,
            crl_uri="http://crl.example.test/tsa.crl",
        )
        good_crl = _crl(signer, root, root_key, now=now)
        revoked_crl = _crl(signer, root, root_key, now=now, revoked_at=now - timedelta(minutes=5))
        stale_crl = _crl(
            signer, root, root_key, now=now,
            next_update=now - timedelta(minutes=1),
        )
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        invalid_signature = _crl(signer, root, wrong_key, now=now)

        for payload, expected in (
            (good_crl, "GOOD"),
            (revoked_crl, "REVOKED"),
            (stale_crl, "UNAVAILABLE"),
            (invalid_signature, "UNAVAILABLE"),
        ):
            with self.subTest(expected=expected), patch.object(
                rfc3161_validation, "_fetch", return_value=payload,
            ):
                result, artifacts = rfc3161_validation._crl_status(signer, root, now)
            self.assertEqual(result["status"], expected)
            self.assertEqual(len(artifacts), 1 if expected != "UNAVAILABLE" else 0)

    def test_ocsp_certid_signature_and_revocation_status(self):
        now = datetime.now(timezone.utc)
        root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OCSP Test Root")])
        root = _certificate(root_name, root_name, root_key.public_key(), root_key, ca=True)
        signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signer_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "OCSP Test Signer")])
        signer = _certificate(
            signer_name, root, signer_key.public_key(), root_key, ca=False,
            ocsp_uri="http://ocsp.example.test",
        )
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Other TSA")])
        other = _certificate(other_name, root, other_key.public_key(), root_key, ca=False)
        responder_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        responder_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Delegated OCSP Responder")])
        responder = _certificate(
            responder_name, root, responder_key.public_key(), root_key, ca=False,
            eku=[ExtendedKeyUsageOID.OCSP_SIGNING],
            key_usage=x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False,
                crl_sign=False, encipher_only=None, decipher_only=None,
            ),
        )
        responses = (
            (_ocsp_response(
                signer, root, root_key, now=now, status=ocsp.OCSPCertStatus.GOOD,
            ), "GOOD"),
            (_ocsp_response(
                signer, root, root_key, now=now,
                status=ocsp.OCSPCertStatus.REVOKED,
                revoked_at=now - timedelta(minutes=5),
            ), "REVOKED"),
            (_ocsp_response(
                other, root, root_key, now=now, status=ocsp.OCSPCertStatus.GOOD,
            ), "UNAVAILABLE"),
            (_ocsp_response(
                signer, root, root_key, now=now, status=ocsp.OCSPCertStatus.GOOD,
                next_update=now - timedelta(minutes=1),
            ), "UNAVAILABLE"),
            (_ocsp_response(
                signer, root, root_key, now=now, status=ocsp.OCSPCertStatus.REVOKED,
                revoked_at=now + timedelta(minutes=5),
            ), "GOOD"),
            (_ocsp_response(
                signer, root, responder_key, now=now, status=ocsp.OCSPCertStatus.GOOD,
                responder=responder, responder_key=responder_key, include_responder=True,
            ), "GOOD"),
        )

        for payload, expected in responses:
            with self.subTest(expected=expected), patch.object(
                rfc3161_validation, "_fetch", return_value=payload,
            ):
                result, artifacts = rfc3161_validation._ocsp_status(signer, root, now)
            self.assertEqual(result["status"], expected)
            self.assertEqual(len(artifacts), 1 if expected != "UNAVAILABLE" else 0)


if __name__ == "__main__":
    unittest.main()
