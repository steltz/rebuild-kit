# auth-reset (designed-not-built)

<!-- Status: designed-not-built. Fills in as-built as M2 closes. -->

As designed (WO-005/WO-006): the visible contract is frozen — same 200/429/403 responses,
same rate limit (3/hour, rolling), same 30-minute window, same single-use semantics, same
deliberate "invalid_token" non-disclosure for expired and unknown tokens alike. What
changes is everything the caller can't see (PB-002 / ED-002):

- tokens become ≥128-bit CSPRNG values; the DB stores only a SHA-256 hash
  (`docs/migration/target-schema.sql` reset_tokens);
- rows carry a real `expires_at` and can be purged (legacy's immortal expired rows —
  DNP-003 — are not ported);
- consumption is atomic (DELETE..RETURNING), closing legacy's confirm race;
- the token mail rides the outbox like every other mail (ED-003).

Open items that shape this area: OQ-002 (bypass header keep/drop) and OQ-006 (who consumes
confirm's `{ok, email}`) — both flagged at the M2 gate.
