# 05 — Password-reset token redesign

## Findings in legacy (all flagged by security)

1. Token is `md5(f"{email}{time.time()}")` — **guessable**: MD5 of a low-entropy input; an
   attacker who knows the target email and approximate request time can brute-force the
   timestamp offline and mint valid tokens.
2. Tokens stored **in plaintext** in `reset_tokens` — a DB read (backup leak, SQL
   injection elsewhere, laptop copy of the sqlite file) yields live reset capability.
3. Bare table: no PK, no index, no expiry column (expiry computed in code), rows never
   cleaned up — expired tokens accumulate forever.
4. Check-then-delete race in confirm: two concurrent confirms of the same token can both
   succeed.
5. Undocumented `X-Internal-Bypass: 1` header disables rate limiting for anyone who knows
   it (see Q2).

## New design

- **Generation**: `secrets.token_urlsafe(32)` (256 bits CSPRNG). The plaintext token
  appears exactly once: in the outbound email body (`reset token: <token>`), preserving the
  legacy email sentence shape.
- **Storage**: only `sha256(token)` (`token_hash BYTEA UNIQUE`), plus `created_at`,
  `expires_at = created_at + RESET_WINDOW_MIN` (config, default 30 — same as legacy),
  `used_at`. Schema in `03-data-model.md`.
- **Confirm** is one atomic statement — closes the race (finding 4):

  ```sql
  UPDATE reset_tokens
     SET used_at = now()
   WHERE token_hash = sha256(:token)
     AND used_at IS NULL
     AND expires_at > now()
  RETURNING email;
  ```

  0 rows → 403 `{"error": "invalid_token"}` — same body for wrong, expired, and reused
  tokens (legacy's deliberate non-disclosure, inventory 6.1, extended to "used").
- **Rate limiting**: unchanged semantics — 3 per rolling hour per email, counted by
  `created_at` over `reset_tokens` (rows are kept ≥1 h so the count works). 429
  `{"error": "rate_limited"}`. Bypass header behavior per Q2 (default: config-gated, off).
- **Non-disclosure**: `POST /api/auth/reset` returns 200 `{"ok": true}` for any email,
  known or not (inventory 5.1). Do not add an existence check.
- **Cleanup**: worker (or a daily job) deletes rows where
  `created_at < now() - interval '24 hours'` — old enough to be irrelevant to both expiry
  (30 min) and rate limiting (1 h).
- **No migration** of legacy tokens (see 03): all are expired by cutover; start empty.

## Explicitly unchanged / out of scope

- There is still no password anywhere in this system — `users` has no credential column and
  there is no login endpoint. `confirm` returns `{"email": ...}` to some upstream consumer
  that presumably completes the actual credential change (Q4). The rewrite reproduces the
  token brokerage exactly; it does not take over password storage.
- Token TTL stays 30 minutes; single-use stays single-use.

## Acceptance checklist (mirrored in verification)

- [ ] No `md5` / `hashlib.md5` anywhere in the new codebase (`grep -ri md5`).
- [ ] DB never contains a plaintext token (inspect rows after a reset request).
- [ ] Same token confirmed twice concurrently → exactly one 200.
- [ ] Expired token (advance clock / shrink config window) → 403 `invalid_token`, body
      byte-identical to the wrong-token response.
- [ ] 4th reset request within an hour for one email → 429.
- [ ] Reset for unknown email → 200 `{"ok": true}` and an outbox row is still created
      (matches legacy, which emailed unknown addresses too).
