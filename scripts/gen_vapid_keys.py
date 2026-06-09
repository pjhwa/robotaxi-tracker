#!/usr/bin/env python3
"""One-time script to generate VAPID keys. Run once, save output to .env."""
import base64
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

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

os.makedirs("vapid", exist_ok=True)
with open("vapid/private_key.pem", "wb") as f:
    f.write(pem)

print(f"VAPID_PUBLIC_KEY={public_b64}")
print("VAPID_CLAIM_EMAIL=inlinetoday@gmail.com")
print()
print("vapid/private_key.pem 저장 완료. 위 두 줄을 .env에 추가하세요.")
