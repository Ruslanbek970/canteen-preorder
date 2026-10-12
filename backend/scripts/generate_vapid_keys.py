"""Prints a fresh VAPID key pair for Web Push; paste both lines into .env.

python -m scripts.generate_vapid_keys
"""

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01, b64urlencode


def generate() -> tuple[str, str]:
    vapid = Vapid01()
    vapid.generate_keys()
    private = vapid.private_key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64urlencode(private), b64urlencode(public)


def main() -> None:
    private, public = generate()
    print(f"VAPID_PRIVATE_KEY={private}")
    print(f"VAPID_PUBLIC_KEY={public}")


if __name__ == "__main__":
    main()
