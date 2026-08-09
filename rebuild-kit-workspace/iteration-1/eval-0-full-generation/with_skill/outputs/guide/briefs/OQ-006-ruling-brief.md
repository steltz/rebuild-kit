# Ruling needed: OQ-006 — Who consumes reset-confirm's `{ok, email}`?

**What's being decided.** Nothing in this repo *does* anything with a confirmed reset:
`users` has no password column (`ticketd/db/schema.sql:12-16`), and confirm just returns
`{"ok": true, "email": ...}` (`ticketd/app/server.py:108`). Something outside — the UI, an
SSO hook, a human process — presumably acts on that response. We need to know what, so the
PB-002 token repair can't accidentally break it.

**Why it's ambiguous.**
- Reading A: a downstream consumer completes a credential change using the returned email
  — evidence: the flow exists and is used (59 requests in 30 days).
- Reading B: the endpoint IS the whole flow (email round-trip as identity proof) —
  evidence: nothing else exists in the repo.

**Where it bites.** WO-006 (M2). Not blocking — the observable contract is implemented
exactly either way — but the M2 gate-signer should know the answer before sign-off, and
NFR-3's "tokens unusable if leaked" reasoning depends on what a confirmed reset *grants*.

**Options & consequences.**
1. Tell us the consumer → we add it to `integration-notes.md`; contract stays frozen.
2. Nobody knows → treat the response as load-bearing verbatim (current plan), and consider
   a follow-up investigation outside this rewrite.

**Recommendation (non-binding).** One Slack message to whoever owns svc-ui probably
settles it.

---
Ruling: ____________  Ruled by: ________  Date: ______
