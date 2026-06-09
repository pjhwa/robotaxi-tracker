#!/usr/bin/env python3
"""One-time script to generate VAPID keys. Run once, save output to .env."""
import base64
import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAPID_DIR = PROJECT_ROOT / "vapid"
KEY_PATH = VAPID_DIR / "private_key.pem"

if __name__ == "__main__":
    if KEY_PATH.exists():
        sys.exit("Key already exists — delete vapid/private_key.pem to regenerate")

    key = ec.generate_private_key(ec.SECP256R1())

    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    pub = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(pub).rstrip(b"=").decode()

    VAPID_DIR.mkdir(exist_ok=True)
    KEY_PATH.write_bytes(pem)
    KEY_PATH.chmod(0o600)

    claim_email = os.environ.get("VAPID_CLAIM_EMAIL", "inlinetoday@gmail.com")

    print(f"VAPID_PUBLIC_KEY={public_b64}")
    print(f"VAPID_CLAIM_EMAIL={claim_email}")
    print()
    print(f"vapid/private_key.pem 저장 완료. 위 두 줄을 .env에 추가하세요.")
