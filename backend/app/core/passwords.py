from __future__ import annotations

import hashlib
import hmac
import os

_ALGORITHM = "sha256"
_ITERATIONS = 120000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(_ALGORITHM, password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        prefix, raw_iterations, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if not prefix.startswith("pbkdf2_"):
            return False
        algorithm = prefix.removeprefix("pbkdf2_")
        iterations = int(raw_iterations)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(algorithm, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)

