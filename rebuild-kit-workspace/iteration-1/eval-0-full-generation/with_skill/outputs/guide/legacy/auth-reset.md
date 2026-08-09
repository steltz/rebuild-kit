# auth-reset (how it works today)

The churn hotspot: three of the legacy repo's four commits are reset-flow hotfixes
(`hotspots.md`). Two routes.

**Request** (`POST /api/auth/reset`): take any email string — no format check, no check
that the user exists (`docs/domain/reset-token.md`) — mint a token, store it, email it.
The token is `md5(email + time.time())`, stored **cleartext** in a bare table with no
primary key, no index, no expiry column (`ticketd/app/server.py:90-92`,
`ticketd/db/schema.sql:18-22`). This is what security flagged: PB-002, and the rewrite
replaces the whole storage scheme (random token, hashed at rest — ED-002) while keeping
every *visible* behavior.

Around it, a rate limit: three requests per email per rolling hour, then 429 — unless the
request carries `X-Internal-Bypass: 1`, an undocumented header that skips the check
entirely (`ticketd/app/server.py:84`). Nobody recorded who uses it or why: **OQ-002,
ruling needed.** One subtlety the traces froze: bypassed requests still insert rows, so
they count toward later non-bypassed checks (RR-4, trace `auth-reset-req-007`).

**Confirm** (`POST /api/auth/reset/confirm`): look the token up; if unknown *or* older
than 30 minutes, answer 403 `{"error":"invalid_token"}` — deliberately the same body for
both causes, so a caller can't probe which tokens exist (`ticketd/app/server.py:104`,
comment says "deliberate"). A valid token is deleted (single-use) and the reply is
`{ok: true, email}` — and here the trail ends: the `users` table has no password column,
so what that email is *for* is unknown outside this repo (**OQ-006**).

Expired tokens, by the way, are never cleaned up — they fail confirmation and sit there
forever (DNP-003: the modern store expires rows; the accumulation is not ported).
Storyboard: `guide/flows/password-reset.md`.
