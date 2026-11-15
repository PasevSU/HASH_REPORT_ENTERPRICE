"""Independent RFC 3161 TSA certificate, chain and revocation validation.

OpenSSL verifies the CMS signer and builds the certificate path; cryptography
checks timestamp-purpose extensions and signed CRL/OCSP evidence. Network
revocation failures are explicit UNAVAILABLE results, never interpreted as GOOD.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import certifi
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, ed448, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7
from cryptography.x509 import ocsp
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID

_TIMESTAMPING_EKU = "1.3.6.1.5.5.7.3.8"
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_TIMEOUT_SECONDS = 12


def _run_openssl(openssl: str, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [openssl, *args], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail[-2000:] or f"OpenSSL failed with exit code {result.returncode}")
    return result


def _parse_time(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    formats = (
        "%b %d %H:%M:%S %Y GMT",
        "%b %d %H:%M:%S.%f %Y GMT",
        "%b %d %H:%M:%S %Y UTC",
        "%b %d %H:%M:%S.%f %Y UTC",
    )
    for format_string in formats:
        try:
            return datetime.strptime(normalized, format_string).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse RFC 3161 genTime: {value!r}")


def _cert_pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(Encoding.PEM)


def _verify_signature(public_key: Any, signature: bytes, data: bytes, algorithm: Any, parameters: Any = None) -> None:
    if isinstance(public_key, rsa.RSAPublicKey):
        scheme = parameters if isinstance(parameters, padding.AsymmetricPadding) else padding.PKCS1v15()
        public_key.verify(signature, data, scheme, algorithm)
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        public_key.verify(signature, data, ec.ECDSA(algorithm))
    elif isinstance(public_key, dsa.DSAPublicKey):
        public_key.verify(signature, data, algorithm)
    elif isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
        public_key.verify(signature, data)
    else:
        raise ValueError(f"Unsupported signature public key: {type(public_key).__name__}")


def _verify_cert_signature(cert: x509.Certificate, issuer: x509.Certificate) -> None:
    _verify_signature(
        issuer.public_key(), cert.signature, cert.tbs_certificate_bytes,
        cert.signature_hash_algorithm, getattr(cert, "signature_algorithm_parameters", None),
    )


def _cert_time_bounds(cert: x509.Certificate) -> tuple[datetime, datetime]:
    before = getattr(cert, "not_valid_before_utc", None)
    after = getattr(cert, "not_valid_after_utc", None)
    if before is None:
        before = cert.not_valid_before.replace(tzinfo=timezone.utc)
    if after is None:
        after = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return before, after


def _fetch(url: str, *, data: bytes | None = None, content_type: str | None = None) -> bytes:
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("PKI distribution points must use HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in PKI distribution-point URLs are not permitted")
    try:
        addresses = {
            ipaddress.ip_address(item[4][0].split("%", 1)[0])
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        }
        if not addresses or any(not address.is_global for address in addresses):
            raise ValueError("PKI distribution-point host resolves to a non-public address")
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError(f"Cannot resolve PKI distribution-point host: {exc}") from exc
    headers = {"Accept": "*/*", "User-Agent": "ChronoSeal RFC3161 validator"}
    if content_type:
        headers["Content-Type"] = content_type
    request = requests.get if data is None else requests.post
    with request(
        url, data=data, headers=headers, timeout=_TIMEOUT_SECONDS,
        allow_redirects=False, stream=True,
    ) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("Redirects from PKI distribution points are not followed")
        response.raise_for_status()
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > _MAX_RESPONSE_BYTES:
                raise ValueError("PKI response exceeds the 8 MiB safety limit")
            chunks.append(chunk)
        if total == 0:
            raise ValueError("PKI endpoint returned an empty response")
        return b"".join(chunks)


def _extension_uris(cert: x509.Certificate, extension_oid: x509.ObjectIdentifier) -> list[str]:
    try:
        extension = cert.extensions.get_extension_for_oid(extension_oid).value
    except x509.ExtensionNotFound:
        return []
    if isinstance(extension, x509.AuthorityInformationAccess):
        return [
            item.access_location.value for item in extension
            if isinstance(item.access_location, x509.UniformResourceIdentifier)
        ]
    if isinstance(extension, x509.CRLDistributionPoints):
        found = []
        for point in extension:
            for name in point.full_name or ():
                if isinstance(name, x509.UniformResourceIdentifier):
                    found.append(name.value)
        return found
    return []


def _subject_public_key_bits(cert: x509.Certificate) -> bytes:
    spki = cert.public_key().public_bytes(
        Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    def read_tlv(data: bytes, offset: int) -> tuple[int, bytes, int]:
        tag = data[offset]
        offset += 1
        length = data[offset]
        offset += 1
        if length & 0x80:
            count = length & 0x7F
            if count == 0 or count > 4:
                raise ValueError("Invalid DER length in SubjectPublicKeyInfo")
            length = int.from_bytes(data[offset:offset + count], "big")
            offset += count
        end = offset + length
        if end > len(data):
            raise ValueError("Truncated DER SubjectPublicKeyInfo")
        return tag, data[offset:end], end

    tag, sequence, end = read_tlv(spki, 0)
    if tag != 0x30 or end != len(spki):
        raise ValueError("Invalid SubjectPublicKeyInfo sequence")
    _, _, position = read_tlv(sequence, 0)
    bit_tag, bit_string, _ = read_tlv(sequence, position)
    if bit_tag != 0x03 or not bit_string or bit_string[0] != 0:
        raise ValueError("Invalid SubjectPublicKeyInfo bit string")
    return bit_string[1:]


def _load_certificates(data: bytes, *, strict: bool = True) -> list[x509.Certificate]:
    pem_blocks = re.findall(
        rb"-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----",
        data,
    )
    if pem_blocks:
        certificates = []
        failures = []
        for block in pem_blocks:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    cert = x509.load_pem_x509_certificate(block)
                    if cert.serial_number <= 0:
                        raise ValueError("Certificate serial number must be positive")
                certificates.append(cert)
            except (ValueError, TypeError) as exc:
                failures.append(str(exc))
        if strict and failures:
            raise ValueError("Invalid certificate in PEM bundle: " + "; ".join(failures))
        if certificates:
            return certificates
        raise ValueError("PEM bundle contains no usable certificates")
    try:
        cert = x509.load_der_x509_certificate(data)
        if cert.serial_number <= 0:
            raise ValueError("Certificate serial number must be positive")
        return [cert]
    except ValueError:
        certificates = list(pkcs7.load_der_pkcs7_certificates(data))
        if any(cert.serial_number <= 0 for cert in certificates):
            raise ValueError("PKCS#7 bundle contains a certificate with a non-positive serial")
        return certificates


def _configured_certificates(variable: str) -> list[tuple[x509.Certificate, bytes, str]]:
    value = os.environ.get(variable, "").strip()
    if not value:
        return []
    try:
        paths = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{variable} must contain a JSON array of certificate paths") from exc
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        raise ValueError(f"{variable} must contain a JSON array of certificate paths")
    certificates = []
    seen = set()
    for item in paths:
        path = Path(item).expanduser().resolve(strict=True)
        if not path.is_file():
            raise FileNotFoundError(f"Configured certificate is not a file: {path}")
        data = path.read_bytes()
        for cert in _load_certificates(data):
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            if fingerprint not in seen:
                seen.add(fingerprint)
                certificates.append((cert, data, path.name))
    return certificates


def _find_issuer(
    cert: x509.Certificate,
    embedded: list[x509.Certificate],
) -> tuple[x509.Certificate, list[dict[str, Any]]]:
    candidates = [candidate for candidate in embedded if candidate.subject == cert.issuer and candidate != cert]
    for candidate in candidates:
        try:
            _verify_cert_signature(cert, candidate)
            return candidate, []
        except Exception:
            continue

    from cryptography.x509.oid import AuthorityInformationAccessOID
    failures = []
    for uri in _extension_uris(cert, ExtensionOID.AUTHORITY_INFORMATION_ACCESS):
        try:
            # Only certificate-issuer locations are useful for path construction.
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
            if not any(
                item.access_method == AuthorityInformationAccessOID.CA_ISSUERS
                and isinstance(item.access_location, x509.UniformResourceIdentifier)
                and item.access_location.value == uri
                for item in aia
            ):
                continue
            data = _fetch(uri)
            for candidate in _load_certificates(data):
                if candidate.subject == cert.issuer:
                    _verify_cert_signature(cert, candidate)
                    return candidate, [{
                        "filename": f"RFC3161_CA_ISSUER_{hashlib.sha256(data).hexdigest()[:12]}.der",
                        "kind": "X509_CA_ISSUER",
                        "data": data,
                    }]
        except Exception as exc:
            failures.append(f"{uri}: {exc}")
    detail = "; ".join(failures)
    raise ValueError("TSA signer issuer certificate is unavailable" + (f": {detail}" if detail else ""))


def _certificate_path(
    signer: x509.Certificate,
    candidates: list[x509.Certificate],
) -> list[x509.Certificate]:
    """Build the unambiguous issuer path using verified certificate signatures."""
    unique = {}
    for candidate in candidates:
        unique[candidate.fingerprint(hashes.SHA256())] = candidate
    candidates = list(unique.values())
    path = [signer]
    seen = {signer.fingerprint(hashes.SHA256())}
    current = signer
    for _ in range(12):
        if current.subject == current.issuer:
            try:
                _verify_cert_signature(current, current)
                return path
            except Exception:
                return path
        parents = []
        for candidate in candidates:
            fingerprint = candidate.fingerprint(hashes.SHA256())
            if fingerprint in seen or candidate.subject != current.issuer:
                continue
            try:
                _verify_cert_signature(current, candidate)
                parents.append(candidate)
            except Exception:
                continue
        if len(parents) != 1:
            return path
        current = parents[0]
        path.append(current)
        seen.add(current.fingerprint(hashes.SHA256()))
    return path


def _parse_crl(data: bytes) -> x509.CertificateRevocationList:
    try:
        return x509.load_pem_x509_crl(data)
    except ValueError:
        return x509.load_der_x509_crl(data)


def _crl_status(cert: x509.Certificate, issuer: x509.Certificate, gen_time: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    uris = _extension_uris(cert, ExtensionOID.CRL_DISTRIBUTION_POINTS)
    if not uris:
        return {"status": "UNAVAILABLE", "detail": "No CRL Distribution Point is present"}, []
    failures = []
    for index, uri in enumerate(uris, 1):
        if not uri.lower().startswith(("http://", "https://")):
            continue
        try:
            data = _fetch(uri)
            crl = _parse_crl(data)
            if crl.issuer != issuer.subject:
                raise ValueError("CRL issuer does not match the TSA signer issuer")
            _verify_signature(
                issuer.public_key(), crl.signature, crl.tbs_certlist_bytes,
                crl.signature_hash_algorithm, getattr(crl, "signature_algorithm_parameters", None),
            )
            last_update = getattr(crl, "last_update_utc", None)
            if last_update is None:
                last_update = crl.last_update.replace(tzinfo=timezone.utc)
            next_update = getattr(crl, "next_update_utc", None)
            if next_update is None and crl.next_update:
                next_update = crl.next_update.replace(tzinfo=timezone.utc)
            if last_update > gen_time or next_update is None or gen_time > next_update:
                raise ValueError("CRL is not fresh at the timestamp's genTime")
            revoked = crl.get_revoked_certificate_by_serial_number(cert.serial_number)
            if revoked is not None:
                revoked_at = getattr(revoked, "revocation_date_utc", None)
                if revoked_at is None:
                    revoked_at = revoked.revocation_date.replace(tzinfo=timezone.utc)
                status = "REVOKED" if revoked_at <= gen_time else "GOOD"
            else:
                status = "GOOD"
            artifact = {
                "filename": f"RFC3161_{index}_CRL_{hashlib.sha256(data).hexdigest()[:12]}.crl",
                "kind": "CRL",
                "data": data,
            }
            return {
                "status": status,
                "detail": f"Signature valid; CRL covers genTime ({last_update.isoformat()} to {next_update.isoformat()})",
                "source": uri,
            }, [artifact]
        except (requests.RequestException, ValueError, TypeError, x509.ExtensionNotFound) as exc:
            failures.append(f"{uri}: {exc}")
        except Exception as exc:
            failures.append(f"{uri}: CRL validation failed: {exc}")
    return {
        "status": "UNAVAILABLE",
        "detail": "; ".join(failures) if failures else "No supported HTTP(S) CRL endpoint",
    }, []


def _responder_certificate(response: ocsp.OCSPResponse, issuer: x509.Certificate) -> x509.Certificate:
    candidates = [*response.certificates, issuer]
    for cert in candidates:
        if response.responder_name is not None and cert.subject == response.responder_name:
            return cert
        if response.responder_key_hash is not None:
            try:
                if hashlib.sha1(_subject_public_key_bits(cert)).digest() == response.responder_key_hash:
                    return cert
            except Exception:
                continue
    raise ValueError("OCSP responder certificate is missing from response and issuer chain")


def _ocsp_status(cert: x509.Certificate, issuer: x509.Certificate, gen_time: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from cryptography.x509.oid import AuthorityInformationAccessOID
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
    except x509.ExtensionNotFound:
        aia = []
    uris = [
        item.access_location.value for item in aia
        if item.access_method == AuthorityInformationAccessOID.OCSP
        and isinstance(item.access_location, x509.UniformResourceIdentifier)
    ]
    if not uris:
        return {"status": "UNAVAILABLE", "detail": "No OCSP responder URI is present"}, []
    failures = []
    for index, uri in enumerate(uris, 1):
        if not uri.lower().startswith(("http://", "https://")):
            continue
        try:
            builder = ocsp.OCSPRequestBuilder().add_certificate(cert, issuer, hashes.SHA1())
            request = builder.build()
            request_der = request.public_bytes(Encoding.DER)
            data = _fetch(uri, data=request_der, content_type="application/ocsp-request")
            response = ocsp.load_der_ocsp_response(data)
            if response.response_status is not ocsp.OCSPResponseStatus.SUCCESSFUL:
                raise ValueError(f"OCSP responder status is {response.response_status.name}")
            responder = _responder_certificate(response, issuer)
            if responder != issuer:
                if responder.issuer != issuer.subject:
                    raise ValueError("OCSP responder certificate is not issued by the TSA certificate issuer")
                _verify_cert_signature(responder, issuer)
                try:
                    eku = responder.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE).value
                except x509.ExtensionNotFound as exc:
                    raise ValueError("Delegated OCSP responder lacks Extended Key Usage") from exc
                if ExtendedKeyUsageOID.OCSP_SIGNING not in eku:
                    raise ValueError("Delegated OCSP responder is not authorized for OCSP signing")
                try:
                    key_usage = responder.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
                except x509.ExtensionNotFound:
                    key_usage = None
                if key_usage is not None and not key_usage.digital_signature:
                    raise ValueError("Delegated OCSP responder key usage does not permit digital signatures")
                produced_at = getattr(
                    response, "produced_at_utc", None,
                )
                if produced_at is None:
                    produced_at = response.produced_at.replace(tzinfo=timezone.utc)
                before, after = _cert_time_bounds(responder)
                if not before <= produced_at <= after:
                    raise ValueError("OCSP responder certificate is not valid when the response was produced")
            _verify_signature(
                responder.public_key(), response.signature, response.tbs_response_bytes,
                response.signature_hash_algorithm, getattr(response, "signature_algorithm_parameters", None),
            )
            this_update = getattr(response, "this_update_utc", None)
            if this_update is None:
                this_update = response.this_update.replace(tzinfo=timezone.utc)
            next_update = getattr(response, "next_update_utc", None)
            if next_update is None and response.next_update:
                next_update = response.next_update.replace(tzinfo=timezone.utc)
            if this_update > gen_time or next_update is None or gen_time > next_update:
                raise ValueError("OCSP response is not fresh at the timestamp's genTime")
            if response.serial_number != cert.serial_number:
                raise ValueError("OCSP response serial number does not match TSA signer")
            if (
                response.hash_algorithm.name != request.hash_algorithm.name
                or response.issuer_name_hash != request.issuer_name_hash
                or response.issuer_key_hash != request.issuer_key_hash
            ):
                raise ValueError("OCSP response CertID does not match TSA signer and issuer")
            if response.certificate_status is ocsp.OCSPCertStatus.REVOKED:
                revocation_time = getattr(response, "revocation_time_utc", None)
                if revocation_time is None:
                    revocation_time = response.revocation_time.replace(tzinfo=timezone.utc)
                status = "REVOKED" if revocation_time <= gen_time else "GOOD"
            elif response.certificate_status is ocsp.OCSPCertStatus.GOOD:
                status = "GOOD"
            else:
                status = "UNKNOWN"
            artifact = {
                "filename": f"RFC3161_{index}_OCSP_{hashlib.sha256(data).hexdigest()[:12]}.ocsp",
                "kind": "OCSP_RESPONSE",
                "data": data,
            }
            return {
                "status": status,
                "detail": f"Signed response covers genTime ({this_update.isoformat()} to {next_update.isoformat()})",
                "source": uri,
            }, [artifact]
        except (requests.RequestException, ValueError, TypeError, x509.ExtensionNotFound) as exc:
            failures.append(f"{uri}: {exc}")
        except Exception as exc:
            failures.append(f"{uri}: OCSP validation failed: {exc}")
    return {
        "status": "UNAVAILABLE",
        "detail": "; ".join(failures) if failures else "No supported HTTP(S) OCSP endpoint",
    }, []


def _openssl_path(openssl_path: str | os.PathLike[str] | None) -> str:
    if openssl_path:
        path = str(openssl_path)
        if Path(path).is_file():
            return path
        raise FileNotFoundError(f"OpenSSL executable not found: {path}")
    import shutil
    found = shutil.which("openssl")
    if not found:
        raise FileNotFoundError("OpenSSL executable was not found")
    return found


def validate_rfc3161_token(
    *,
    token_der: bytes,
    marker: str,
    openssl_path: str | os.PathLike[str] | None,
    gen_time_text: str,
) -> dict[str, Any]:
    """Validate the embedded CMS signer, RFC 3161 EKU, chain and revocation."""
    if not isinstance(token_der, bytes) or not token_der:
        raise ValueError("token_der must be non-empty DER bytes")
    timestamp = _parse_time(gen_time_text)
    openssl = _openssl_path(openssl_path)
    artifacts: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="chronoseal-rfc3161-validation-") as temporary:
        temp = Path(temporary)
        token_path = temp / "token.der"
        signer_path = temp / "signer.pem"
        payload_path = temp / "signed-content.der"
        token_path.write_bytes(token_der)

        _run_openssl(openssl, [
            "cms", "-verify", "-binary", "-inform", "DER", "-in", str(token_path),
            "-noverify", "-signer", str(signer_path), "-out", str(payload_path),
        ])
        if not signer_path.is_file():
            raise ValueError("OpenSSL did not identify the CMS SignerInfo certificate")
        signer = x509.load_pem_x509_certificate(signer_path.read_bytes())
        try:
            certificates = pkcs7.load_der_pkcs7_certificates(token_der)
        except ValueError as exc:
            raise ValueError("RFC 3161 CMS token has no valid certificate set") from exc
        if not certificates:
            raise ValueError("RFC 3161 CMS token contains no certificates")

        signer_fingerprint = signer.fingerprint(hashes.SHA256()).hex()
        embedded_fingerprints = {cert.fingerprint(hashes.SHA256()).hex() for cert in certificates}
        if signer_fingerprint not in embedded_fingerprints:
            raise ValueError("CMS signer certificate is not present in the token certificate set")
        try:
            eku_extension = signer.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
        except x509.ExtensionNotFound as exc:
            raise ValueError("TSA signer certificate lacks Extended Key Usage") from exc
        if not eku_extension.critical:
            raise ValueError("TSA signer Extended Key Usage is not critical")
        if list(eku_extension.value) != [ExtendedKeyUsageOID.TIME_STAMPING]:
            raise ValueError("TSA signer Extended Key Usage must be limited to time stamping")
        try:
            key_usage = signer.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
        except x509.ExtensionNotFound:
            key_usage = None
        if key_usage is not None and not key_usage.digital_signature:
            raise ValueError("TSA signer certificate key usage does not permit digital signatures")
        not_before, not_after = _cert_time_bounds(signer)
        if not not_before <= timestamp <= not_after:
            raise ValueError("TSA signer certificate is not valid at the RFC 3161 genTime")

        issuer, fetched_issuer_artifacts = _find_issuer(signer, certificates)
        if issuer.fingerprint(hashes.SHA256()).hex() not in embedded_fingerprints:
            certificates.append(issuer)
            embedded_fingerprints.add(issuer.fingerprint(hashes.SHA256()).hex())
        artifacts.extend(fetched_issuer_artifacts)

        intermediate_certs = [cert for cert in certificates if cert not in (signer, issuer)]
        configured_roots = _configured_certificates("CHRONOSEAL_TSA_TRUST_ROOTS")
        configured_intermediates = _configured_certificates("CHRONOSEAL_TSA_INTERMEDIATES")
        for cert, data, name in configured_intermediates:
            if cert not in intermediate_certs and cert not in (signer, issuer):
                intermediate_certs.append(cert)
            artifacts.append({
                "filename": f"RFC3161_{marker}_INTERMEDIATE_{cert.fingerprint(hashes.SHA256()).hex()[:16]}.pem",
                "kind": "X509_INTERMEDIATE",
                "marker": marker,
                "data": _cert_pem(cert),
                "source_name": name,
            })
        ca_bundle = Path(certifi.where()).read_bytes()
        bundled_roots = _load_certificates(ca_bundle, strict=False)
        trust_names: dict[str, str] = {}
        repository_root = Path(__file__).resolve().parents[1]
        if str(repository_root) not in sys.path:
            sys.path.insert(0, str(repository_root))
        try:
            from bridge.trust_anchors import EXTENDED_TRUST_ANCHORS
            trust_names = EXTENDED_TRUST_ANCHORS
        except ImportError:
            trust_names = {}
        configured_root_certs = []
        for cert, data, name in configured_roots:
            if cert.subject != cert.issuer:
                raise ValueError(f"Configured trust root is not self-issued: {name}")
            try:
                constraints = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value
            except x509.ExtensionNotFound as exc:
                raise ValueError(f"Configured trust root lacks Basic Constraints: {name}") from exc
            if not constraints.ca:
                raise ValueError(f"Configured trust certificate is not a CA: {name}")
            _verify_cert_signature(cert, cert)
            configured_root_certs.append(cert)
            artifacts.append({
                "filename": f"RFC3161_{marker}_TRUST_ROOT_{cert.fingerprint(hashes.SHA256()).hex()[:16]}.pem",
                "kind": "X509_TRUST_ANCHOR",
                "marker": marker,
                "data": _cert_pem(cert),
                "source_name": name,
            })
        pinned_roots = []
        for cert in [*certificates, *[item[0] for item in configured_roots]]:
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            if fingerprint not in trust_names or cert.subject != cert.issuer:
                continue
            try:
                _verify_cert_signature(cert, cert)
            except Exception:
                continue
            pinned_roots.append(cert)
        path_candidates = [
            *certificates,
            *[item[0] for item in configured_intermediates],
            *[item[0] for item in configured_roots],
            *bundled_roots,
            *pinned_roots,
        ]
        certificate_path = _certificate_path(signer, path_candidates)
        path_root = certificate_path[-1]
        configured_root_hashes = {
            cert.fingerprint(hashes.SHA256()).hex() for cert in configured_root_certs
        }
        pinned_root_hashes = {
            cert.fingerprint(hashes.SHA256()).hex() for cert in pinned_roots
        }
        bundled_root_hashes = {
            cert.fingerprint(hashes.SHA256()).hex() for cert in bundled_roots
        }
        path_root_hash = path_root.fingerprint(hashes.SHA256()).hex()
        if path_root_hash in configured_root_hashes:
            root_trust_status = "PASS (explicitly configured trust root)"
        elif path_root_hash in pinned_root_hashes:
            root_trust_status = "PASS (pinned trust root)"
        elif path_root_hash in bundled_root_hashes:
            root_trust_status = "PASS (bundled CA trust store)"
        else:
            root_trust_status = "UNAVAILABLE (root certificate not identified)"
        trust_bundle_path = temp / "trusted-roots.pem"
        with trust_bundle_path.open("wb") as bundle:
            bundle.write(ca_bundle)
            if not ca_bundle.endswith(b"\n"):
                bundle.write(b"\n")
            for cert in [*pinned_roots, *configured_root_certs]:
                bundle.write(_cert_pem(cert))
        chain_result = "UNAVAILABLE"
        chain_detail = ""
        try:
            chain_args = [
                "verify", "-purpose", "timestampsign", "-attime", str(int(timestamp.timestamp())),
                "-CAfile", str(trust_bundle_path),
            ]
            untrusted_certs = [issuer, *intermediate_certs]
            if untrusted_certs:
                intermediate_path = temp / "intermediates.pem"
                with intermediate_path.open("wb") as bundle:
                    for cert in untrusted_certs:
                        bundle.write(_cert_pem(cert))
                chain_args.extend(["-untrusted", str(intermediate_path)])
            chain_args.append(str(signer_path))
            result = _run_openssl(openssl, chain_args)
            chain_result = "GOOD"
            chain_detail = result.stdout.strip() or "Certificate chain verified against the configured trust bundle"
            if pinned_roots:
                chain_detail += "; trusted pinned root(s): " + ", ".join(
                    trust_names[cert.fingerprint(hashes.SHA256()).hex()] for cert in pinned_roots
                )
            if configured_root_certs:
                chain_detail += "; explicitly configured trust root(s): " + ", ".join(
                    cert.subject.rfc4514_string() for cert in configured_root_certs
                )
        except RuntimeError as exc:
            chain_result = "FAILED"
            chain_detail = str(exc)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            chain_detail = str(exc)
        for cert in certificates:
            pem = _cert_pem(cert)
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            artifacts.append({
                "filename": f"RFC3161_{marker}_CERT_{fingerprint[:16]}.pem",
                "kind": "X509_CERTIFICATE",
                "marker": marker,
                "sha256": hashlib.sha256(pem).hexdigest(),
                "certificate_sha256_fingerprint": fingerprint,
                "data": pem,
            })

        crl, crl_artifacts = _crl_status(signer, issuer, timestamp)
        ocsp_result, ocsp_artifacts = _ocsp_status(signer, issuer, timestamp)
        artifacts.extend(crl_artifacts)
        artifacts.extend(ocsp_artifacts)

    lines = [
        f"  • TSA Signer Certificate: {signer.subject.rfc4514_string()}",
        f"  • TSA Signer SHA-256: {signer_fingerprint}",
        f"  • TSA Signer Issuer: {signer.issuer.rfc4514_string()}",
        "  • TSA Signer EKU Time Stamping: PASS (critical EKU)",
        "  • TSA Signer Valid at genTime: PASS",
        f"  • Root CA SHA-256: {path_root_hash}",
        f"  • Root Trust Anchor Check: {root_trust_status}",
        f"  • Certificate Chain: {chain_result} ({chain_detail})",
        f"  • CRL Revocation Status: {crl['status']} ({crl['detail']})",
        f"  • OCSP Revocation Status: {ocsp_result['status']} ({ocsp_result['detail']})",
    ]
    return {
        "marker": marker,
        "gen_time": timestamp.isoformat(),
        "signer_subject": signer.subject.rfc4514_string(),
        "signer_issuer": signer.issuer.rfc4514_string(),
        "signer_serial": format(signer.serial_number, "X"),
        "signer_sha256": signer_fingerprint,
        "root_sha256": path_root_hash,
        "root_trust_status": root_trust_status,
        "certificate_path": [cert.subject.rfc4514_string() for cert in certificate_path],
        "certificate_path_sha256": [
            cert.fingerprint(hashes.SHA256()).hex().upper()
            for cert in certificate_path
        ],
        "chain": {"status": chain_result, "detail": chain_detail},
        "crl": crl,
        "ocsp": ocsp_result,
        "lines": lines,
        "artifacts": artifacts,
    }
