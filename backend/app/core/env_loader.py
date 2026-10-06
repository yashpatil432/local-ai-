"""
LocalLens Environment & SSL Security Manager
=============================================
Safely loads API credentials from .env and configures SSL trust bundles
for Windows environments (preventing CERTIFICATE_VERIFY_FAILED errors caused
by local antivirus or proxy SSL inspection).
"""

import os
import ssl
import certifi
import requests
from typing import Optional, Dict, Any

# Cached CA bundle path
_MERGED_CA_BUNDLE: Optional[str] = None
_API_KEY: Optional[str] = None


def get_merged_ca_bundle() -> str:
    """
    Returns the path to a combined PEM bundle containing both certifi's Mozilla root CAs
    and Windows System Root CAs (including local antivirus roots like Avast/AVG).
    """
    global _MERGED_CA_BUNDLE
    if _MERGED_CA_BUNDLE and os.path.exists(_MERGED_CA_BUNDLE):
        return _MERGED_CA_BUNDLE

    ca_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), ".locallens_certs")
    os.makedirs(ca_dir, exist_ok=True)
    bundle_path = os.path.join(ca_dir, "merged_ca_bundle.pem")

    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with open(bundle_path, "wb") as out_f:
                # 1. Base certifi certificates
                if os.path.exists(certifi.where()):
                    with open(certifi.where(), "rb") as cf:
                        out_f.write(cf.read())
                        out_f.write(b"\n")

                # 2. Windows Root Certificate Store
                if hasattr(ssl, "enum_certificates"):
                    for cert_bytes, _, _ in ssl.enum_certificates("ROOT"):
                        try:
                            cert = x509.load_der_x509_certificate(cert_bytes)
                            out_f.write(cert.public_bytes(serialization.Encoding.PEM))
                            out_f.write(b"\n")
                        except Exception:
                            pass
        _MERGED_CA_BUNDLE = bundle_path
    except Exception:
        _MERGED_CA_BUNDLE = certifi.where()

    # Configure environment variables for child processes/libraries
    os.environ["SSL_CERT_FILE"] = _MERGED_CA_BUNDLE
    os.environ["REQUESTS_CA_BUNDLE"] = _MERGED_CA_BUNDLE
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = _MERGED_CA_BUNDLE

    return _MERGED_CA_BUNDLE


def load_environment_credentials() -> Dict[str, str]:
    """
    Finds and parses .env file from project root or current directory.
    Handles both standard 'KEY=VALUE' and Windows 'set KEY=VALUE' syntax.
    """
    global _API_KEY
    env_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
        os.path.abspath(os.path.join(os.getcwd(), ".env")),
        os.path.abspath(".env")
    ]

    loaded: Dict[str, str] = {}

    for path in env_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Handle 'set KEY=VAL' or 'KEY=VAL'
                    if line.lower().startswith("set "):
                        line = line[4:].strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and v:
                            loaded[k] = v
                            os.environ[k] = v

    # Extract Gemini / Gemma API key
    _API_KEY = (
        loaded.get("GEMINI_API_KEY") 
        or loaded.get("GOOGLE_API_KEY") 
        or os.environ.get("GEMINI_API_KEY") 
        or os.environ.get("GOOGLE_API_KEY")
    )
    return loaded


def get_gemini_api_key() -> Optional[str]:
    """
    Returns the loaded Gemini / Gemma API key.
    """
    global _API_KEY
    if not _API_KEY:
        load_environment_credentials()
    return _API_KEY


# Initialize immediately upon import
load_environment_credentials()
get_merged_ca_bundle()
