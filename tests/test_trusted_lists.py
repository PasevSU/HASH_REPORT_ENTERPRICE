import base64
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner, SignatureReference, methods

from chronoseal.trusted_lists import verify_lotl_and_member_tsl, verify_qualified_tsa_service_status

NS = "http://uri.etsi.org/02231/v2#"
URL = "https://crc.example/tsl.xml"
XADES = "http://uri.etsi.org/01903/v1.3.2#"


def _identity(name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _signed_tree(root, key, cert):
    properties = etree.SubElement(root, f"{{{XADES}}}SignedProperties", Id="xades-props")
    signature_properties = etree.SubElement(properties, f"{{{XADES}}}SignedSignatureProperties")
    signing_certificate = etree.SubElement(signature_properties, f"{{{XADES}}}SigningCertificateV2")
    cert_item = etree.SubElement(signing_certificate, f"{{{XADES}}}Cert")
    cert_digest = etree.SubElement(cert_item, f"{{{XADES}}}CertDigest")
    etree.SubElement(
        cert_digest,
        f"{{http://www.w3.org/2000/09/xmldsig#}}DigestMethod",
        Algorithm="http://www.w3.org/2001/04/xmlenc#sha512",
    )
    digest = etree.SubElement(cert_digest, f"{{http://www.w3.org/2000/09/xmldsig#}}DigestValue")
    digest.text = base64.b64encode(cert.fingerprint(hashes.SHA512())).decode("ascii")
    signed = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha512",
        digest_algorithm="sha512",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    ).sign(
        root,
        key=key,
        cert=cert.public_bytes(serialization.Encoding.PEM),
        reference_uri=[f"#{root.get('Id')}", SignatureReference("#xades-props")],
        id_attribute="Id",
    )
    references = signed.findall(f".//{{http://www.w3.org/2000/09/xmldsig#}}Reference")
    references[1].set("Type", "http://uri.etsi.org/01903#SignedProperties")
    transforms = references[1].find(f"{{http://www.w3.org/2000/09/xmldsig#}}Transforms")
    transforms.remove(transforms[0])
    signed_info = signed.find(f".//{{http://www.w3.org/2000/09/xmldsig#}}SignedInfo")
    signed_value = signed.find(f".//{{http://www.w3.org/2000/09/xmldsig#}}SignatureValue")
    canonical_signed_info = etree.tostring(signed_info, method="c14n", exclusive=True)
    signed_value.text = base64.b64encode(
        key.sign(canonical_signed_info, padding.PKCS1v15(), hashes.SHA512())
    ).decode("ascii")
    return signed


def _resign_signed_info(signature, key):
    signed_info = signature.find(f".//{{http://www.w3.org/2000/09/xmldsig#}}SignedInfo")
    signed_value = signature.find(f".//{{http://www.w3.org/2000/09/xmldsig#}}SignatureValue")
    canonical_signed_info = etree.tostring(signed_info, method="c14n", exclusive=True)
    signed_value.text = base64.b64encode(
        key.sign(canonical_signed_info, padding.PKCS1v15(), hashes.SHA512())
    ).decode("ascii")


def _list_root(identifier, territory):
    root = etree.Element(f"{{{NS}}}TrustServiceStatusList", nsmap={None: NS}, Id=identifier)
    info = etree.SubElement(root, f"{{{NS}}}SchemeInformation")
    etree.SubElement(info, f"{{{NS}}}TSLVersionIdentifier").text = "6"
    etree.SubElement(info, f"{{{NS}}}TSLSequenceNumber").text = "1"
    etree.SubElement(info, f"{{{NS}}}SchemeTerritory").text = territory
    etree.SubElement(root, f"{{{NS}}}SignedPayload", Id="payload-id").text = "covered"
    return root


class TrustedListTests(unittest.TestCase):
    def test_accepts_tlv6_whole_document_empty_uri_reference(self):
        from chronoseal.trusted_lists import verify_signed_list
        with tempfile.TemporaryDirectory() as temporary:
            key, cert = _identity("TLv6 signer")
            xml = _signed_tree(_list_root("bg-id", "BG"), key, cert)
            references = xml.findall(f".//{{http://www.w3.org/2000/09/xmldsig#}}Reference")
            references[0].set("URI", "")
            _resign_signed_info(xml, key)
            path = Path(temporary) / "bg.xml"
            path.write_bytes(etree.tostring(xml, encoding="UTF-8"))
            result = verify_signed_list(
                path,
                cert,
                expected_fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
                expected_territory="BG",
            )
            self.assertEqual(result["status"], "SIGNATURE_VALID")

    def test_verifies_lotl_pin_delegation_and_member_tsl_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            lotl_key, lotl_cert = _identity("Pinned LOTL signer")
            bg_key, bg_cert = _identity("Delegated BG TSL signer")
            lotl = _list_root("lotl-id", "EU")
            pointers = etree.SubElement(lotl.find(f"./{{{NS}}}SchemeInformation"), f"{{{NS}}}PointersToOtherTSL")
            pointer = etree.SubElement(pointers, f"{{{NS}}}OtherTSLPointer")
            additional = etree.SubElement(pointer, f"{{{NS}}}AdditionalInformation")
            other = etree.SubElement(additional, f"{{{NS}}}OtherInformation")
            etree.SubElement(other, f"{{{NS}}}SchemeTerritory").text = "BG"
            etree.SubElement(pointer, f"{{{NS}}}TSLLocation").text = URL
            identities = etree.SubElement(pointer, f"{{{NS}}}ServiceDigitalIdentities")
            identity = etree.SubElement(identities, f"{{{NS}}}ServiceDigitalIdentity")
            digital_id = etree.SubElement(identity, f"{{{NS}}}DigitalId")
            encoded = base64.b64encode(bg_cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
            etree.SubElement(digital_id, f"{{{NS}}}X509Certificate").text = encoded
            signed_lotl = _signed_tree(lotl, lotl_key, lotl_cert)
            lotl_file = folder / "lotl.xml"
            lotl_file.write_bytes(etree.tostring(signed_lotl, xml_declaration=True, encoding="UTF-8"))
            anchor_file = folder / "lotl-signer.pem"
            anchor_file.write_bytes(lotl_cert.public_bytes(serialization.Encoding.PEM))

            signed_bg = _signed_tree(_list_root("bg-id", "BG"), bg_key, bg_cert)
            bg_file = folder / "bg.xml"
            bg_file.write_bytes(etree.tostring(signed_bg, xml_declaration=True, encoding="UTF-8"))

            result = verify_lotl_and_member_tsl(
                lotl_path=lotl_file,
                lotl_signer_certificate_path=anchor_file,
                lotl_signer_sha256=lotl_cert.fingerprint(hashes.SHA256()).hex(),
                member_tsl_path=bg_file,
                member_tsl_url=URL,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["lotl"]["status"], "SIGNATURE_VALID")
            self.assertEqual(result["member_tsl"]["territory"], "BG")
            self.assertEqual(result["delegated_signer_sha256"], bg_cert.fingerprint(hashes.SHA256()).hex().upper())

    def test_rejects_wrong_out_of_band_lotl_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            key, cert = _identity("Wrong pin")
            anchor_file = folder / "pin.pem"
            anchor_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            lotl_file = folder / "lotl.xml"
            lotl_file.write_text("<not-a-list/>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match its independently provisioned"):
                verify_lotl_and_member_tsl(
                    lotl_path=lotl_file,
                    lotl_signer_certificate_path=anchor_file,
                    lotl_signer_sha256="0" * 64,
                    member_tsl_path=lotl_file,
                    member_tsl_url=URL,
                )

    def test_rejects_unverified_lotl_pointer_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            lotl_key, lotl_cert = _identity("Pinned LOTL signer")
            bg_key, bg_cert = _identity("Delegated BG TSL signer")
            lotl = _list_root("lotl-id", "EU")
            pointers = etree.SubElement(lotl.find(f"./{{{NS}}}SchemeInformation"), f"{{{NS}}}PointersToOtherTSL")
            pointer = etree.SubElement(pointers, f"{{{NS}}}OtherTSLPointer")
            additional = etree.SubElement(pointer, f"{{{NS}}}AdditionalInformation")
            other = etree.SubElement(additional, f"{{{NS}}}OtherInformation")
            etree.SubElement(other, f"{{{NS}}}SchemeTerritory").text = "BG"
            etree.SubElement(pointer, f"{{{NS}}}TSLLocation").text = URL
            identities = etree.SubElement(pointer, f"{{{NS}}}ServiceDigitalIdentities")
            identity = etree.SubElement(identities, f"{{{NS}}}ServiceDigitalIdentity")
            digital_id = etree.SubElement(identity, f"{{{NS}}}DigitalId")
            encoded = base64.b64encode(bg_cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
            etree.SubElement(digital_id, f"{{{NS}}}X509Certificate").text = encoded
            lotl_file = folder / "lotl.xml"
            lotl_file.write_bytes(etree.tostring(_signed_tree(lotl, lotl_key, lotl_cert), encoding="UTF-8"))
            anchor_file = folder / "anchor.pem"
            anchor_file.write_bytes(lotl_cert.public_bytes(serialization.Encoding.PEM))
            bg_file = folder / "bg.xml"
            wrong_key, wrong_cert = _identity("Not delegated")
            bg_file.write_bytes(etree.tostring(_signed_tree(_list_root("bg-id", "BG"), wrong_key, wrong_cert), encoding="UTF-8"))
            with self.assertRaisesRegex(ValueError, "not delegated"):
                verify_lotl_and_member_tsl(
                    lotl_path=lotl_file,
                    lotl_signer_certificate_path=anchor_file,
                    lotl_signer_sha256=lotl_cert.fingerprint(hashes.SHA256()).hex(),
                    member_tsl_path=bg_file,
                    member_tsl_url=URL,
                )

    def test_rejects_modified_signed_member_tsl(self):
        from chronoseal.trusted_lists import verify_signed_list
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            key, cert = _identity("Member signer")
            xml = _signed_tree(_list_root("bg-id", "BG"), key, cert)
            xml.find(f"./{{{NS}}}SignedPayload").text = "modified"
            member_file = folder / "member.xml"
            member_file.write_bytes(etree.tostring(xml, encoding="UTF-8"))
            with self.assertRaisesRegex(ValueError, "signature validation failed"):
                verify_signed_list(
                    member_file,
                    cert,
                    expected_fingerprint=cert.fingerprint(hashes.SHA256()).hex(),
                    expected_territory="BG",
                )

    def test_service_status_is_evaluated_at_requested_instant(self):
        with tempfile.TemporaryDirectory() as temporary:
            key, cert = _identity("B-Trust QTSA identity")
            root = _list_root("bg-id", "BG")
            service = etree.SubElement(root, f"{{{NS}}}TSPService")
            info = etree.SubElement(service, f"{{{NS}}}ServiceInformation")
            service_name = etree.SubElement(info, f"{{{NS}}}ServiceName")
            etree.SubElement(service_name, f"{{{NS}}}Name", **{"{http://www.w3.org/XML/1998/namespace}lang": "en"}).text = "B-Trust QTSA"
            etree.SubElement(info, f"{{{NS}}}ServiceTypeIdentifier").text = "http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST"
            etree.SubElement(info, f"{{{NS}}}ServiceStatus").text = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted"
            etree.SubElement(info, f"{{{NS}}}StatusStartingTime").text = "2026-01-01T00:00:00Z"
            identities = etree.SubElement(info, f"{{{NS}}}ServiceDigitalIdentities")
            identity = etree.SubElement(identities, f"{{{NS}}}ServiceDigitalIdentity")
            digital_id = etree.SubElement(identity, f"{{{NS}}}DigitalId")
            etree.SubElement(digital_id, f"{{{NS}}}X509Certificate").text = base64.b64encode(
                cert.public_bytes(serialization.Encoding.DER)
            ).decode("ascii")
            path = Path(temporary) / "service.xml"
            path.write_bytes(etree.tostring(root, encoding="UTF-8"))
            result = verify_qualified_tsa_service_status(
                path,
                service_name="B-Trust QTSA",
                service_certificate_sha256=cert.fingerprint(hashes.SHA256()).hex(),
                at_time=datetime(2026, 10, 9, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "GRANTED")
            self.assertTrue(result["identity_present_in_effective_status"])

    def test_service_status_does_not_apply_before_start_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, cert = _identity("B-Trust QTSA identity")
            root = _list_root("bg-id", "BG")
            service = etree.SubElement(root, f"{{{NS}}}TSPService")
            info = etree.SubElement(service, f"{{{NS}}}ServiceInformation")
            name = etree.SubElement(info, f"{{{NS}}}ServiceName")
            etree.SubElement(name, f"{{{NS}}}Name").text = "B-Trust QTSA"
            etree.SubElement(info, f"{{{NS}}}ServiceTypeIdentifier").text = "http://uri.etsi.org/TrstSvc/Svctype/TSA/QTST"
            etree.SubElement(info, f"{{{NS}}}ServiceStatus").text = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted"
            etree.SubElement(info, f"{{{NS}}}StatusStartingTime").text = "2026-01-01T00:00:00Z"
            identities = etree.SubElement(info, f"{{{NS}}}ServiceDigitalIdentities")
            identity = etree.SubElement(identities, f"{{{NS}}}ServiceDigitalIdentity")
            digital_id = etree.SubElement(identity, f"{{{NS}}}DigitalId")
            etree.SubElement(digital_id, f"{{{NS}}}X509Certificate").text = base64.b64encode(
                cert.public_bytes(serialization.Encoding.DER)
            ).decode("ascii")
            path = Path(temporary) / "service.xml"
            path.write_bytes(etree.tostring(root, encoding="UTF-8"))
            with self.assertRaisesRegex(ValueError, "found 0"):
                verify_qualified_tsa_service_status(
                    path,
                    service_name="B-Trust QTSA",
                    service_certificate_sha256=cert.fingerprint(hashes.SHA256()).hex(),
                    at_time=datetime(2025, 10, 9, tzinfo=timezone.utc),
                )


if __name__ == "__main__":
    unittest.main()
