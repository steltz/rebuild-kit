"""
Fixes Known Problem #2: password-reset tokens were MD5(email + time.time())
(ticketd/app/server.py:90) — deterministic-ish and not a secret-grade random
value.

Replacement:
- The plaintext token handed to the user (via email) is `secrets.token_urlsafe`,
  which draws from the OS CSPRNG.
- Only a SHA-256 hash of that token is ever written to the database
  (see app.models.ResetToken), so a DB read/leak alone does not yield a
  usable token.
- Lookups hash the incoming token and compare against the stored hash.

This changes internal storage only. The external contract — a token string
in the email, POSTed back to /api/auth/reset/confirm — is unchanged.
"""
import hashlib
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    """Used for the preserved (unauthenticated) internal-bypass header check
    in routers/auth.py — see docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md for
    why the header itself is preserved rather than removed."""
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
