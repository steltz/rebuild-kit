# ADR-002: Reset tokens — CSPRNG + hashed at rest; bypass header off by default

Status: accepted (safe from source alone). Date: 2026-08-08.

## Problem

Handover problem #2 says "password-reset tokens are MD5". Source (`server.py:90`)
shows it is worse: `md5(f"{email}{time.time()}")` — the *input* is guessable (target's
email + request timestamp to sub-second precision), so tokens are predictable, and they
are stored in plaintext in `reset_tokens`.

Adjacent findings: undocumented `X-Internal-Bypass: 1` header skips the rate limit
(server.py:84, Q11); tokens are minted for any email with no user check; expired
tokens are never purged; rate-limit check-then-insert is racy.

## Decision

1. **Token generation:** `secrets.token_urlsafe(32)` (256-bit CSPRNG).
2. **Storage:** SHA-256 of the token; plaintext exists only in the email. A DB leak no
   longer leaks live tokens. (Plain SHA-256 is fine here — tokens are high-entropy, no
   need for a slow hash.)
3. **Preserved semantics** (all `[S]`, all kept): 30-minute window; single use; rate
   limit 3/hour/email; expired and invalid tokens return identical
   `403 {"error": "invalid_token"}` (Q12 non-disclosure); success returns
   `{"ok": true, "email": ...}` — frozen until the downstream consumer is identified
   (unknown #1 in `../inventory/dead-code-and-unknowns.md`); requests for unknown
   emails still mint + mail a token and return `{"ok": true}`.
4. **Bypass header:** ported but behind `ALLOW_INTERNAL_BYPASS` config, **default
   off**. It is a security hole with unknown callers; if intake items A2/B1 find a
   real caller, re-enable temporarily for that caller and then replace it. If they
   find none, delete the code path.
5. **Hygiene added:** expired-token purge in the outbox worker's idle loop, and the
   rate-limit count runs in the same transaction as the insert.

## Compatibility notes

- Token *format* changes (32-hex MD5 → 43-char urlsafe). Any consumer that validates
  token shape (e.g. a UI regex expecting `[0-9a-f]{32}`) breaks. Flagged for D1/D2
  interviews; parity tests intentionally do NOT assert token format.
- In-flight legacy tokens die at cutover unless migrated; with a 30-minute lifetime,
  a brief freeze on reset requests around cutover is simpler than migrating them.
