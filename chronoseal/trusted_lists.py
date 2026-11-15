"""Offline validation of EU LOTL and delegated national Trusted Lists.

Trust is anchored only by an externally provisioned OJEU LOTL signer
certificate pin. Certificates embedded in a list are never trust anchors unless
the already-verified LOTL delegates that certificate to the relevant territory.
"""
from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from lxml import etree
from signxml import SignatureConfiguration, XMLVerifier, algorithms

TSL_NS = "http://uri.etsi.org/02231/v2#"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
MAX_XML_BYTES = 20 * 1024 * 1024
SHA512_SIGNATURE = algorithms.SignatureMethod.RSA_SHA512
SHA512_DIGEST = algorithms.DigestAlgorithm.SHA512
EXCLUSIVE_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
ENVELOPED_SIGNATURE = f"{DS_NS}enveloped-signature"
SIGNED_PROPERTIES_TYPE = "http://uri.etsi.org/01903#SignedProperties"
XADES_NS_PREFIX = "http://uri.etsi.org/01903/"


def _read_xml(path: str | Path) -> tuple[bytes, etree._Element]:
    file_path = Path(path).expanduser().resolve(strict=True)
    if not file_path.is_file():
        raise ValueError(f"Trusted List input is not a file: {file_path}")
    data = file_path.read_bytes()
    if not data or len(data) > MAX_XML_BYTES:
        raise ValueError(f"Trusted List XML is empty or exceeds {MAX_XML_BYTES} bytes")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        remove_blank_text=False,
    )
    root = etree.fromstring(data, parser=parser)
    if root.getroottree().docinfo.doctype:
        raise ValueError("Trusted List XML must not contain a document type declaration")
    if root.tag != f"{{{TSL_NS}}}TrustServiceStatusList":
        raise ValueError("XML root is not an ETSI Trusted List")
    return data, root


def _certificate(data: bytes) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(data)
    except ValueError:
        return x509.load_der_x509_certificate(data)


def _sha256(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex().upper()


def _check_digest_and_signature_algorithms(signature: etree._Element) -> None:
    signatures = signature.findall(f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}SignatureMethod")
    if len(signatures) != 1 or signatures[0].get("Algorithm") != SHA512_SIGNATURE.value:
        raise ValueError("Trusted List must use the approved RSA-SHA512 XML signature algorithm")
    canonicalization = signature.findall(f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}CanonicalizationMethod")
    if len(canonicalization) != 1 or canonicalization[0].get("Algorithm") != EXCLUSIVE_C14N:
        raise ValueError("Trusted List must use exclusive XML canonicalization")
    references = signature.findall(f"{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference")
    if len(references) != 2:
        raise ValueError(f"Trusted List signature must contain exactly two references (found {len(references)})")
    root_reference = None
    properties_reference = None
    for reference in references:
        if "URI" not in reference.attrib:
            raise ValueError("Trusted List signature references must declare a URI")
        uri = reference.get("URI", "")
        digests = reference.findall(f"{{{DS_NS}}}DigestMethod")
        if len(digests) != 1 or digests[0].get("Algorithm") != SHA512_DIGEST.value:
            raise ValueError("Trusted List signature references must use SHA-512 digests")
        transforms = [
            item.get("Algorithm")
            for item in reference.findall(f"{{{DS_NS}}}Transforms/{{{DS_NS}}}Transform")
        ]
        if (
            root_reference is None
            and not reference.get("Type")
            and transforms == [ENVELOPED_SIGNATURE, EXCLUSIVE_C14N]
            and (uri == "" or uri.startswith("#"))
        ):
            root_reference = reference
        elif uri.startswith("#") and len(uri) > 1 and properties_reference is None:
            if reference.get("Type") != SIGNED_PROPERTIES_TYPE or transforms != [EXCLUSIVE_C14N]:
                raise ValueError("Trusted List second reference must authenticate XAdES SignedProperties")
            properties_reference = reference
        else:
            raise ValueError("Trusted List must contain one whole-document and one XAdES SignedProperties reference")
    if root_reference is None or properties_reference is None:
        raise ValueError("Trusted List signature is missing the whole-document or SignedProperties reference")


def verify_signed_list(
    xml_path: str | Path,
    signer_certificate: x509.Certificate,
    *,
    expected_fingerprint: str,
    expected_territory: str | None = None,
) -> dict[str, Any]:
    expected = str(expected_fingerprint).replace(":", "").strip().upper()
    observed = _sha256(signer_certificate)
    if not re.fullmatch(r"[0-9A-F]{64}", expected) or observed != expected:
        raise ValueError("Trusted List signer certificate does not match its independently provisioned SHA-256 pin")
    data, root = _read_xml(xml_path)
    if expected_territory:
        territory = root.findtext(f"./{{{TSL_NS}}}SchemeInformation/{{{TSL_NS}}}SchemeTerritory")
        if territory != expected_territory:
            raise ValueError(f"Trusted List territory mismatch: expected {expected_territory}, found {territory!r}")

    signatures = root.findall(f".//{{{DS_NS}}}Signature")
    if len(signatures) != 1:
        raise ValueError(f"Trusted List must contain exactly one XML signature (found {len(signatures)})")
    signature = signatures[0]
    _check_digest_and_signature_algorithms(signature)
    embedded = signature.findall(
        f"./{{{DS_NS}}}KeyInfo/{{{DS_NS}}}X509Data/{{{DS_NS}}}X509Certificate"
    )
    if len(embedded) != 1:
        raise ValueError("Trusted List must identify exactly one signer certificate")
    try:
        cert_text = re.sub(r"\s+", "", "".join(embedded[0].itertext()))
        embedded_cert = x509.load_der_x509_certificate(base64.b64decode(cert_text, validate=True))
    except (ValueError, TypeError) as exc:
        raise ValueError("Trusted List embedded signer certificate is malformed") from exc
    if _sha256(embedded_cert) != observed:
        raise ValueError("Trusted List embedded signer certificate does not match the authorized signer")

    # Reject wrapping and external references before handing the document to
    # the XMLDSig implementation. SignXML additionally validates every digest.
    all_ids: dict[str, int] = {}
    for element in root.iter():
        for name, value in element.attrib.items():
            if name.rsplit("}", 1)[-1] == "Id":
                all_ids[value] = all_ids.get(value, 0) + 1
    if any(count != 1 for count in all_ids.values()):
        raise ValueError("Trusted List contains duplicate XML ID attributes")
    for reference in signature.findall(f"./{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference"):
        uri = reference.get("URI", "")
        if uri.startswith("#") and all_ids.get(uri[1:]) != 1:
            raise ValueError(f"Trusted List signature references an absent or ambiguous XML ID: {uri[1:]}")
    root_references = [
        reference
        for reference in signature.findall(f"./{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference")
        if ENVELOPED_SIGNATURE
        in [
            transform.get("Algorithm")
            for transform in reference.findall(f"{{{DS_NS}}}Transforms/{{{DS_NS}}}Transform")
        ]
        and not reference.get("Type")
    ]
    if len(root_references) != 1:
        raise ValueError("Trusted List must contain exactly one enveloped document reference")
    root_reference_uri = root_references[0].get("URI", "")
    if root_reference_uri.startswith("#") and root_reference_uri[1:] != root.get("Id"):
        raise ValueError("Trusted List enveloped reference does not target the document root")
    properties_references = [
        reference
        for reference in signature.findall(f"./{{{DS_NS}}}SignedInfo/{{{DS_NS}}}Reference")
        if reference.get("Type") == SIGNED_PROPERTIES_TYPE
    ]
    if len(properties_references) != 1:
        raise ValueError("Trusted List signature must reference exactly one XAdES SignedProperties element")
    properties_reference = properties_references[0]
    properties_target = properties_reference.get("URI", "")[1:]
    properties_element = next(
        (element for element in root.iter() if element.get("Id") == properties_target),
        None,
    )
    if (
        properties_element is None
        or etree.QName(properties_element).localname != "SignedProperties"
        or not etree.QName(properties_element).namespace.startswith(XADES_NS_PREFIX)
    ):
        raise ValueError("Trusted List SignedProperties reference does not target XAdES SignedProperties")
    signing_certificate = next(
        (
            element
            for element in properties_element.iter()
            if etree.QName(element).localname == "SigningCertificateV2"
            and etree.QName(element).namespace.startswith(XADES_NS_PREFIX)
        ),
        None,
    )
    cert_digest = (
        signing_certificate.find(f".//{{{DS_NS}}}DigestValue")
        if signing_certificate is not None
        else None
    )
    digest_method = (
        signing_certificate.find(f".//{{{DS_NS}}}DigestMethod")
        if signing_certificate is not None
        else None
    )
    if cert_digest is None or not cert_digest.text or digest_method is None:
        raise ValueError("Trusted List XAdES SignedProperties lacks SigningCertificateV2")
    try:
        declared_cert_digest = base64.b64decode(re.sub(r"\s+", "", cert_digest.text), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Trusted List SigningCertificateV2 digest is malformed") from exc
    cert_digest_algorithms = {
        "http://www.w3.org/2001/04/xmlenc#sha256": hashes.SHA256(),
        SHA512_DIGEST.value: hashes.SHA512(),
    }
    digest_algorithm = cert_digest_algorithms.get(digest_method.get("Algorithm"))
    if digest_algorithm is None or declared_cert_digest != signer_certificate.fingerprint(digest_algorithm):
        raise ValueError("Trusted List XAdES SigningCertificateV2 does not bind the expected signer certificate")

    expect = SignatureConfiguration(
        require_x509=True,
        location=".//",
        expect_references=2,
        signature_methods=frozenset({SHA512_SIGNATURE}),
        digest_algorithms=frozenset({SHA512_DIGEST}),
    )
    try:
        verified = XMLVerifier().verify(
            root,
            x509_cert=signer_certificate,
            expect_config=expect,
            id_attribute="Id",
            validate_schema=False,
        )
    except Exception as exc:
        raise ValueError(f"Trusted List XML signature validation failed: {exc}") from exc
    if not isinstance(verified, list) or len(verified) != 2:
        raise ValueError("Trusted List signature validator did not confirm both required references")

    information = root.find(f"./{{{TSL_NS}}}SchemeInformation")
    if information is None:
        raise ValueError("Trusted List SchemeInformation is missing")
    return {
        "status": "SIGNATURE_VALID",
        "sha256": hashlib.sha256(data).hexdigest().upper(),
        "signer_sha256": observed,
        "territory": information.findtext(f"./{{{TSL_NS}}}SchemeTerritory"),
        "version": information.findtext(f"./{{{TSL_NS}}}TSLVersionIdentifier"),
        "sequence": information.findtext(f"./{{{TSL_NS}}}TSLSequenceNumber"),
    }


def verify_lotl_and_member_tsl(
    *,
    lotl_path: str | Path,
    lotl_signer_certificate_path: str | Path,
    lotl_signer_sha256: str,
    member_tsl_path: str | Path,
    member_tsl_url: str,
    territory: str = "BG",
) -> dict[str, Any]:
    """Verify LOTL against an out-of-band pin, then its delegated member TSL."""
    lotl_signer = _certificate(Path(lotl_signer_certificate_path).expanduser().resolve(strict=True).read_bytes())
    lotl = verify_signed_list(
        lotl_path,
        lotl_signer,
        expected_fingerprint=lotl_signer_sha256,
    )
    lotl_data, lotl_root = _read_xml(lotl_path)
    del lotl_data
    pointers = lotl_root.findall(
        f"./{{{TSL_NS}}}SchemeInformation/{{{TSL_NS}}}PointersToOtherTSL/{{{TSL_NS}}}OtherTSLPointer"
    )
    matching = []
    for pointer in pointers:
        pointer_territory = pointer.findtext(
            f"./{{{TSL_NS}}}AdditionalInformation/{{{TSL_NS}}}OtherInformation/"
            f"{{{TSL_NS}}}SchemeTerritory"
        )
        locations = [
            "".join(node.itertext()).strip()
            for node in pointer.findall(f"./{{{TSL_NS}}}TSLLocation")
        ]
        if pointer_territory == territory and member_tsl_url in locations:
            matching.append(pointer)
    if len(matching) != 1:
        raise ValueError(
            f"Verified LOTL must contain exactly one {territory} pointer for {member_tsl_url} (found {len(matching)})"
        )
    delegated_certificates = []
    for node in matching[0].findall(
        f".//{{{TSL_NS}}}ServiceDigitalIdentity/{{{TSL_NS}}}DigitalId/{{{TSL_NS}}}X509Certificate"
    ):
        try:
            cert_text = re.sub(r"\s+", "", "".join(node.itertext()))
            cert = x509.load_der_x509_certificate(base64.b64decode(cert_text, validate=True))
        except (ValueError, TypeError) as exc:
            raise ValueError("Verified LOTL contains a malformed delegated TSL signer certificate") from exc
        if all(_sha256(cert) != _sha256(existing) for existing in delegated_certificates):
            delegated_certificates.append(cert)
    if not delegated_certificates:
        raise ValueError(f"Verified LOTL {territory} pointer does not delegate a TSL signer certificate")

    tsl_data, tsl_root = _read_xml(member_tsl_path)
    del tsl_data
    tsl_signature = tsl_root.findall(f".//{{{DS_NS}}}Signature")
    if len(tsl_signature) != 1:
        raise ValueError(f"Member TSL must contain exactly one XML signature (found {len(tsl_signature)})")
    embedded_nodes = tsl_signature[0].findall(
        f"./{{{DS_NS}}}KeyInfo/{{{DS_NS}}}X509Data/{{{DS_NS}}}X509Certificate"
    )
    if len(embedded_nodes) != 1:
        raise ValueError("Member TSL must identify exactly one signer certificate")
    try:
        member_signer = x509.load_der_x509_certificate(
            base64.b64decode(re.sub(r"\s+", "", "".join(embedded_nodes[0].itertext())), validate=True)
        )
    except (ValueError, TypeError) as exc:
        raise ValueError("Member TSL embedded signer certificate is malformed") from exc
    if not any(_sha256(member_signer) == _sha256(cert) for cert in delegated_certificates):
        raise ValueError("Member TSL signer is not delegated by the verified LOTL pointer")
    tsl = verify_signed_list(
        member_tsl_path,
        member_signer,
        expected_fingerprint=_sha256(member_signer),
        expected_territory=territory,
    )
    return {"status": "PASS", "lotl": lotl, "member_tsl": tsl, "delegated_signer_sha256": _sha256(member_signer)}


def verify_qualified_tsa_service_status(
    tsl_path: str | Path,
    *,
    service_name: str,
    service_certificate_sha256: str,
    at_time: datetime,
) -> dict[str, Any]:
    """Evaluate the TSL service's effective status at a specified instant."""
    if at_time.tzinfo is None:
        raise ValueError("Service status evaluation time must be timezone-aware")
    _, root = _read_xml(tsl_path)
    expected_cert = str(service_certificate_sha256).replace(":", "").strip().upper()
    if not re.fullmatch(r"[0-9A-F]{64}", expected_cert):
        raise ValueError("Invalid TSL service identity SHA-256 fingerprint")
    matches = []
    for service in root.findall(f".//{{{TSL_NS}}}TSPService"):
        info = service.find(f"./{{{TSL_NS}}}ServiceInformation")
        if info is None:
            continue
        name_nodes = info.findall(f"./{{{TSL_NS}}}ServiceName/{{{TSL_NS}}}Name")
        english_names = [
            "".join(node.itertext()).strip()
            for node in name_nodes
            if node.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower().startswith("en")
        ]
        other_names = ["".join(node.itertext()).strip() for node in name_nodes]
        actual_name = next((text for text in english_names if text), next((text for text in other_names if text), ""))
        service_type = (info.findtext(f"./{{{TSL_NS}}}ServiceTypeIdentifier") or "").strip()
        if actual_name != service_name or not service_type.endswith("/TSA/QTST"):
            continue
        timeline = [info, *service.findall(f"./{{{TSL_NS}}}ServiceHistory/{{{TSL_NS}}}ServiceHistoryInstance")]
        events = []
        identity_seen = False
        for item in timeline:
            status = (item.findtext(f"./{{{TSL_NS}}}ServiceStatus") or "").strip()
            starting_text = (item.findtext(f"./{{{TSL_NS}}}StatusStartingTime") or "").strip()
            if not status or not starting_text:
                continue
            try:
                starting = datetime.fromisoformat(starting_text.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"Invalid TSL service StatusStartingTime: {starting_text}") from exc
            if starting.tzinfo is None:
                raise ValueError("TSL service StatusStartingTime must include a timezone")
            cert_hashes = []
            for certificate in item.findall(
                f".//{{{TSL_NS}}}ServiceDigitalIdentity/{{{TSL_NS}}}DigitalId/{{{TSL_NS}}}X509Certificate"
            ):
                cert_text = re.sub(r"\s+", "", "".join(certificate.itertext()))
                try:
                    cert = x509.load_der_x509_certificate(base64.b64decode(cert_text, validate=True))
                except (ValueError, TypeError) as exc:
                    raise ValueError("TSL service identity certificate is malformed") from exc
                cert_hashes.append(_sha256(cert))
            identity_seen = identity_seen or expected_cert in cert_hashes
            events.append((starting.astimezone(timezone.utc), status, cert_hashes))
        if identity_seen:
            eligible = [event for event in events if event[0] <= at_time.astimezone(timezone.utc)]
            if eligible:
                matches.append((actual_name, service_type, max(eligible, key=lambda item: item[0])))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one TSL QTSA service matching the name and pinned identity (found {len(matches)})"
        )
    name, service_type, (starting, status_uri, cert_hashes) = matches[0]
    if status_uri.rstrip("/").endswith("/Svcstatus/granted") is False:
        raise ValueError(f"TSL service is not granted at the requested time: {status_uri}")
    if expected_cert not in cert_hashes:
        raise ValueError("Pinned service identity is not effective at the requested time")
    return {
        "status": "GRANTED",
        "service_name": name,
        "service_type": service_type,
        "effective_status_uri": status_uri,
        "status_starting_time": starting.isoformat(),
        "identity_sha256": expected_cert,
        "identity_present_in_effective_status": expected_cert in cert_hashes,
        "evaluated_at": at_time.astimezone(timezone.utc).isoformat(),
    }
