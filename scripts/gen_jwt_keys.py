#!/usr/bin/env python
"""Generate RS256 keypair cho JWT.

Usage:
    python -m scripts.gen_jwt_keys
    # hoặc chỉ định đường dẫn:
    python -m scripts.gen_jwt_keys --out secrets/

Sinh ra 2 file PEM trong thư mục trước:
    - jwt_rs256.pem        (private)
    - jwt_rs256.pub.pem    (public)

Cập nhật đường dẫn trong .env: AUTH_PRIVATE_KEY_PATH / AUTH_PUBLIC_KEY_PATH.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="backend/secrets", help="Directory chứa key")
    ap.add_argument("--bits", type=int, default=2048, help="Key size (bits)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    priv_path = out_dir / "jwt_rs256.pem"
    pub_path = out_dir / "jwt_rs256.pub.pem"

    if priv_path.exists() and not _confirm_overwrite(priv_path):
        print("Aborted.", file=sys.stderr)
        return 1

    key = rsa.generate_private_key(public_exponent=65537, key_size=args.bits)
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_path.write_bytes(priv_pem)
    priv_path.chmod(0o600)
    pub_path.write_bytes(pub_pem)
    print(f"Private: {priv_path}")
    print(f"Public : {pub_path}")
    print("Add to .env:")
    print(f"  AUTH_PRIVATE_KEY_PATH={priv_path.resolve()}")
    print(f"  AUTH_PUBLIC_KEY_PATH={pub_path.resolve()}")
    return 0


def _confirm_overwrite(path: Path) -> bool:
    return input(f"{path} exists. Overwrite? [y/N] ").strip().lower() in ("y", "yes")


if __name__ == "__main__":
    sys.exit(main())