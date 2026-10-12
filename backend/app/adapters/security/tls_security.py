"""mTLS and Digital Certificate Validation Engine for FBR / PRAL Gateway Integration.

Complies with PRAL Digital Invoicing / POS specifications:
- Client Certificate format validation (X.509 PEM/DER)
- Mutual TLS (mTLS) handshake configuration (TLS 1.2 / TLS 1.3)
- Key length verification (RSA >= 2048-bit or ECC >= 256-bit)
- NTN / Subject metadata extraction and expiry auditing
"""

import os
import ssl
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ec

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class CertificateValidationError(Exception):
    """Raised when an FBR/PRAL digital certificate fails compliance verification."""
    pass


def parse_and_verify_certificate(cert_input: Union[bytes, str, Path]) -> Dict[str, Any]:
    """Parses and audits an X.509 digital certificate against PRAL technical specifications.
    
    Accepts either PEM bytes, a path string, or a Path object.
    """
    cert_bytes: bytes
    if isinstance(cert_input, (str, Path)):
        path = Path(cert_input)
        if not path.is_file():
            raise CertificateValidationError(f"Certificate file not found at path: {cert_input}")
        cert_bytes = path.read_bytes()
    elif isinstance(cert_input, bytes):
        cert_bytes = cert_input
    else:
        raise CertificateValidationError("cert_input must be bytes or a file path string")

    try:
        if b"-----BEGIN CERTIFICATE-----" in cert_bytes:
            cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())
        else:
            cert = x509.load_der_x509_certificate(cert_bytes, default_backend())
    except Exception as exc:
        raise CertificateValidationError(f"Failed to parse X.509 certificate: {exc}") from exc

    now = datetime.now(timezone.utc)
    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        not_before = cert.not_valid_before.replace(tzinfo=timezone.utc)
        not_after = cert.not_valid_after.replace(tzinfo=timezone.utc)

    is_expired = now > not_after
    is_not_yet_valid = now < not_before
    days_left = (not_after - now).days if not is_expired else 0

    # Extract Subject Attributes
    subject_info = {}
    for attr in cert.subject:
        subject_info[attr.oid._name] = attr.value

    # Extract Issuer Attributes
    issuer_info = {}
    for attr in cert.issuer:
        issuer_info[attr.oid._name] = attr.value

    # Evaluate Public Key
    public_key = cert.public_key()
    key_type = "UNKNOWN"
    key_size = 0
    is_key_compliant = False

    if isinstance(public_key, rsa.RSAPublicKey):
        key_type = "RSA"
        key_size = public_key.key_size
        is_key_compliant = key_size >= 2048
    elif isinstance(public_key, ec.EllipticCurvePublicKey):
        key_type = "ECDSA"
        key_size = public_key.key_size
        is_key_compliant = key_size >= 256

    sha256_fp = cert.fingerprint(hashes.SHA256()).hex().upper()
    sha256_formatted = ":".join(sha256_fp[i:i+2] for i in range(0, len(sha256_fp), 2))

    # PRAL Validation Invariants
    validation_errors = []
    if is_expired:
        validation_errors.append(f"Certificate expired on {not_after.isoformat()}")
    if is_not_yet_valid:
        validation_errors.append(f"Certificate is not valid until {not_before.isoformat()}")
    if not is_key_compliant:
        validation_errors.append(f"Key size {key_size}-bit {key_type} is below mandatory minimum (RSA >= 2048 or ECC >= 256)")

    # Attempt to extract NTN from CN or SerialNumber if present
    ntn_candidate = subject_info.get("serialNumber") or subject_info.get("commonName", "")
    has_ntn = any(c.isdigit() for c in ntn_candidate)

    return {
        "is_valid": len(validation_errors) == 0,
        "validation_errors": validation_errors,
        "subject": subject_info,
        "issuer": issuer_info,
        "common_name": subject_info.get("commonName", "N/A"),
        "organization": subject_info.get("organizationName", "N/A"),
        "serial_number": subject_info.get("serialNumber", "N/A"),
        "has_ntn_identifier": has_ntn,
        "not_valid_before": not_before.isoformat(),
        "not_valid_after": not_after.isoformat(),
        "days_remaining": days_left,
        "is_expired": is_expired,
        "key_algorithm": key_type,
        "key_size_bits": key_size,
        "is_key_compliant": is_key_compliant,
        "sha256_fingerprint": sha256_formatted,
        "serial_int": str(cert.serial_number),
    }


def create_fbr_ssl_context(
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
    ca_path: Optional[str] = None,
    passphrase: Optional[str] = None,
) -> ssl.SSLContext:
    """Builds an enterprise-grade mutual TLS SSLContext meeting PRAL/FBR standards.
    
    Enforces TLS 1.2 minimum, disable insecure protocols and ciphers, and binds client credentials.
    """
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    # Restrict ciphers to modern forward-secret suites
    try:
        ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:!aNULL:!eNULL:!MD5:!3DES:!RC4")
    except ssl.SSLError:
        pass  # Platform default if custom cipher string not fully supported

    ca_file = ca_path or settings.FBR_CA_CERT_PATH
    if ca_file and os.path.isfile(ca_file):
        ctx.load_verify_locations(cafile=ca_file)
        logger.info(f"Loaded PRAL Root CA bundle from {ca_file}")

    c_cert = cert_path or settings.FBR_CLIENT_CERT_PATH
    c_key = key_path or settings.FBR_CLIENT_KEY_PATH

    if c_cert and c_key and os.path.isfile(c_cert) and os.path.isfile(c_key):
        ctx.load_cert_chain(
            certfile=c_cert,
            keyfile=c_key,
            password=passphrase.encode("utf-8") if passphrase else None,
        )
        logger.info(f"Configured client mTLS certificate: {c_cert}")

    return ctx


def build_fbr_http_client(
    timeout: float = 15.0,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
    ca_path: Optional[str] = None,
) -> httpx.Client:
    """Instantiates an HTTPX client configured with optional mTLS and custom PRAL SSLContext."""
    c_cert = cert_path or settings.FBR_CLIENT_CERT_PATH
    c_key = key_path or settings.FBR_CLIENT_KEY_PATH
    ca_file = ca_path or settings.FBR_CA_CERT_PATH

    client_cert: Optional[Tuple[str, Optional[str]]] = None
    if c_cert and os.path.isfile(c_cert):
        if c_key and os.path.isfile(c_key):
            client_cert = (c_cert, c_key)
        else:
            client_cert = (c_cert, None)

    verify_target: Union[bool, str] = True
    if ca_file and os.path.isfile(ca_file):
        verify_target = ca_file

    return httpx.Client(
        cert=client_cert,
        verify=verify_target,
        timeout=timeout,
        headers={"User-Agent": "FBR-Invoice-Cloud-PRAL-Client/1.1"},
    )


def generate_self_signed_certification_cert(
    output_dir: Union[str, Path],
    org_name: str = "Test Taxpayer Distribution Ltd",
    ntn: str = "1234567-8",
    common_name: str = "pos-client-10001.fbr.local",
    validity_days: int = 365,
) -> Tuple[Path, Path]:
    """Generates an RSA-2048 compliance test certificate and private key for sandbox mTLS certification."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cert_path = out_path / "sandbox_client_cert.pem"
    key_path = out_path / "sandbox_client_key.pem"

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(x509.NameOID.COUNTRY_NAME, "PK"),
        x509.NameAttribute(x509.NameOID.STATE_OR_PROVINCE_NAME, "Sindh"),
        x509.NameAttribute(x509.NameOID.LOCALITY_NAME, "Karachi"),
        x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, org_name),
        x509.NameAttribute(x509.NameOID.SERIAL_NUMBER, ntn),
        x509.NameAttribute(x509.NameOID.COMMON_NAME, common_name),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    return cert_path, key_path
