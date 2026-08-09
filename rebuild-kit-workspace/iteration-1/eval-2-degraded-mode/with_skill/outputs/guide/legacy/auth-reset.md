# auth-reset (how it works today)

Two routes (`ticketd/app/server.py:80-108`), one constraint-free table (`reset_tokens`), and
a mystery: **nothing in this codebase consumes a completed reset.** There is no login, no
password column, and the `users` table is read by no code path — confirm just echoes the
email back and deletes the token (OQ-002). Either an external system calls this, or it's
vestigial.

## Request (`POST /api/auth/reset`)
Any email string is accepted — empty, unknown, never checked against `users` — and the
answer is always `{"ok": true}` (account-enumeration-safe, plausibly deliberate). The token
is `md5(email + time.time())`, stored **in plaintext** (PB-002), and mailed synchronously in
the request thread (PB-001).

**The rate limit is subtler than it looks** (audit finding A-01): 429 fires when ≥3 rows
for that email survive in the table from the last hour. Confirming a token *deletes its row
and refunds quota* — verified live: 3 requests, confirm one, and a 4th request succeeds
(traces rlr-request-004-after-refund → 200, rlr-request-005 → 429). Expired-but-unconfirmed
tokens still count for the full hour. And `X-Internal-Bypass: 1` — undocumented,
unauthenticated — skips the check entirely (OQ-004: tool dependency or backdoor?).

## Confirm (`POST /api/auth/reset/confirm`)
Token lookup only, no email cross-check. Expired (>30 min) and unknown tokens return the
**identical** 403 body — the comment marks the non-disclosure deliberate (server.py:104).
Valid → row deleted (single-use), 200 with the email echo. Expired rows are never purged;
the table has grown since 2019 (size unknown until census — OQ-INT-2).

## What the rewrite changes here
Token mechanism only: CSPRNG, hashed at rest (ED-003), queued email (ED-002). The window,
single-use rule, non-disclosure wall, refund-flavored rate limit, and always-ok responses
are all frozen and trace-pinned.

Evidence base: docs/features/draft/auth-reset.md (audited), traces reset-* and rlr-* in
verification/replay/traces/.
