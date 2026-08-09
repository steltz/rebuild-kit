# **Auth/Reset** (how it works today)

Two routes, and despite the name this is the *entire* auth surface of the app — there's no login,
no session, no password field anywhere in the schema. "Reset" doesn't reset anything observable;
the token's only effect is being deletable. Full detail: `docs/features/draft/auth-reset.md`,
`docs/domain/reset_token.md`.

**Request** (`POST /api/auth/reset`) takes any string as an email — never validated as looking
like one, never checked against a real user — rate-limits to 3/hour per exact email match, and
mints a token via `hashlib.md5(f"{email}{time.time()}")`. That's PB-002: not cryptographically
random, and stored as plaintext in a table with no index, no primary key, and no expiry sweep —
rows for abandoned flows just accumulate forever. There's also an undocumented escape hatch: a
header called `X-Internal-Bypass` skips the rate limit entirely. Nobody knows anymore whether
that's a deliberate internal-service allowance or forgotten debug scaffolding (PB-008/OQ-002) —
and this rewrite deliberately isn't guessing.

**Confirm** (`POST /api/auth/reset/confirm`) checks a 30-minute expiry window and — this is a nice
touch, worth preserving exactly — returns the *identical* error for a token that's expired and one
that never existed at all. A code comment confirms this is deliberate non-disclosure, not an
oversight. A P9 audit found a real gap here too: every trace in this workspace that exercises this
error path actually hits the "token not found" branch (because the token was already consumed by
a prior confirm), not the "genuinely still-present-but-time-expired" branch — the claim that both
produce the same response is still true by direct source reading, but nobody has actually captured
the second case yet.
