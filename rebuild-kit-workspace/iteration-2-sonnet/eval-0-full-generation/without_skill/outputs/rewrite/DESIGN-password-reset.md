# Design: secure password-reset tokens (fixes the security flag)

## The problem, precisely

```python
token = hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()
db().execute("INSERT INTO reset_tokens (email, token, created_ts) VALUES (?, ?, ?)",
             (email, token, time.time()))
```

Two independent weaknesses, both need fixing:

1. **MD5** is fast and not designed for this use case (not that this would
   matter much once #2 is fixed, but it's what security actually flagged).
2. **The token isn't a secret — it's a hash of guessable inputs.** `email` is
   often known to an attacker, and `time.time()` at the moment of the
   request is guessable to within seconds (the request's own timestamp is
   visible in a `Date` header, and `RESET_WINDOW_MIN = 30` gives an attacker
   a 30-minute-wide, sub-second-granularity search space to brute force
   offline — an MD5 hash over that space is fast to exhaust with commodity
   hardware). Hashing with SHA-256 instead of MD5 alone would not fix this;
   the real bug is that the "secret" isn't secret.
3. Stored in **plaintext** in a table with no PK/index — anyone with read
   access to that table (a DB backup, a misconfigured replica, a compromised
   read-only reporting role) can use any live token directly.

## Fix

**Generate a real random secret; store only a hash of it.**

```python
import secrets, hashlib

raw_token = secrets.token_urlsafe(32)          # ~256 bits of entropy, this IS the secret
token_hash = hashlib.sha256(raw_token.encode()).hexdigest()  # what we store

# INSERT INTO reset_tokens (email, token_hash, created_at, expires_at)
# VALUES (?, ?, now(), now() + interval '30 minutes')

send_mail(email, f"reset token: {raw_token}")   # raw token leaves the system only via email
```

On confirm:
```python
token_hash = hashlib.sha256(submitted_token.encode()).hexdigest()
row = lookup_by_token_hash(token_hash)
if row is None or row.used_at is not None or row.expires_at < now():
    return 403, {"error": "invalid_token"}   # SAME body for all three cases — non-disclosure preserved
mark_used(row)
return 200, {"ok": True, "email": row.email}
```

Why this is enough without a KDF (bcrypt/argon2/scrypt): those exist to slow
down brute-forcing of *low-entropy, human-chosen* secrets (passwords).
`raw_token` is a 256-bit *machine-generated* random value — the search space
is astronomically larger than any KDF work-factor could meaningfully defend
against or need to slow down further. A plain fast hash (SHA-256) is the
correct and standard tool for "prove you hold this random token" (this is
the same pattern OAuth refresh tokens, API keys, and session tokens
typically use). Do not reach for bcrypt here — that would be solving a
different problem than the one that exists.

## What must NOT change (API contract, preserved from behavior contract)

- `POST /api/auth/reset` response: `{"ok": true}` — same for real and
  fabricated emails (anti-enumeration; unchanged, since we still never check
  `email` against `users`).
- `POST /api/auth/reset/confirm`:
  - success → `200 {"ok": true, "email": <str>}`
  - invalid, expired, OR already-used token → `403 {"error":
    "invalid_token"}`, **identical body in all three cases**. The new schema
    adds `used_at`, which makes "already used" a real, checkable state for
    the first time (legacy deletes the row instead) — the observable
    response must still collapse all three into the same error, or this
    becomes an oracle (an attacker could learn "this token existed and was
    already used" vs. "this token never existed," which the legacy system
    also didn't leak, since it just returns 403 either way).
- Rate limiting (`RATE_LIMIT_PER_HOUR = 3` per email per rolling hour) and
  the `X-Internal-Bypass: 1` header — preserved as-is, pending
  `03-OPEN-QUESTIONS.md` item 4 on whether the bypass header itself should
  be reworked. Do not silently drop or silently keep it without reading that
  open question.
- Token lifetime: `RESET_WINDOW_MIN = 30` minutes — unchanged unless
  leadership says otherwise.

## Migration note

Legacy `reset_tokens` rows (plaintext MD5-derived tokens) are **not**
migrated into the new table. They cannot be represented in the new schema
(we'd have to store a plaintext token or a hash of a value we don't trust,
defeating the point), and by the time of any real cutover window they'll be
well past the 30-minute expiry anyway. Anyone with an in-flight reset at the
moment of cutover just requests a new one. See
`plans/06-migration-and-cutover.md`.
