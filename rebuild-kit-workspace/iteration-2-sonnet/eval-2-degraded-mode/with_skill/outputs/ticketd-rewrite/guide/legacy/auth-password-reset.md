# Auth / Password Reset (how it works today)

Two routes, `legacy/app/server.py:80-108`, backed by a `reset_tokens` table that — unusually for
this codebase — has no primary key at all.

**Request** (`POST /api/auth/reset`) takes a raw email (never checked against any `users` row —
see `docs/open-questions.md#OQ-003`, the `users` table appears to be entirely unused by the
application), rate-limits to 3 requests/hour per email UNLESS the caller sends an undocumented
`X-Internal-Bypass: 1` header (`docs/open-questions.md#OQ-007` — real code, no explanation
anywhere of who's meant to use it), and generates a token as `MD5(email + current_time)`. This is
PB-002, the second of the two problems that motivated this whole rewrite: MD5 of low-entropy
input is not a secure token. Read `guide/flows/password-reset.md` for a real captured trace of
this exact request.

**Confirm** (`POST /api/auth/reset/confirm`) checks the token, and — this is deliberate, not an
oversight — returns the EXACT SAME `403 {"error": "invalid_token"}` whether the token is unknown
or simply expired (30-minute window). This non-disclosure pattern is worth calling out
explicitly: it's the kind of thing that looks fixable but shouldn't be touched without a very
good reason, because the ambiguity is the point (it stops an attacker from learning whether a
guessed token ever existed).

Both routes also hit PB-001 (synchronous email) — this is the SECOND of its two call sites in
the app; see `guide/legacy/notifications.md`.

See `docs/domain/reset-token.md` for the full lifecycle diagram.
