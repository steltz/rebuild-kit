# **Auth/Reset** (designed-not-built)

**Not yet built.** Designed in `docs/features/WO-003-reset-token-mechanism.md` (the token
mechanism itself) and `docs/features/WO-004-auth-reset-endpoints.md` (the two routes).

From the outside, this subsystem should feel identical to legacy: same rate limit (3/hour), same
30-minute expiry, same non-disclosure behavior on confirm. What changes is entirely internal — the
token stops being an MD5 hash of low-entropy input and becomes a real cryptographically random
credential, hashed at rest, with an actual bounded-growth story instead of a table that grows
forever (PB-002, ED-002). WO-003 leaves the exact algorithm as a FREE choice; check
`ledger.json`'s `free_choices` for WO-003 once it's built to see what was picked.

One thing this chapter will NOT show, by design, until a human rules on it: whatever
`X-Internal-Bypass` becomes. WO-004 ships with that specific code path deliberately absent —
neither preserved nor removed — see `briefs/OQ-002-ruling-brief.md`.
