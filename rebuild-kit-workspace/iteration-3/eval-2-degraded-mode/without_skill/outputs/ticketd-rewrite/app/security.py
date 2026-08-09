"""Reset-token generation. Replaces legacy MD5(email+timestamp) — see
docs/DESIGN.md 'Fix 2'.

`generate_reset_token()` returns cryptographically random, unguessable
plaintext (never derived from email/time). Only `hash_token()` of it is
persisted; the plaintext is emailed once and never stored.
"""

import hashlib
import secrets


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
