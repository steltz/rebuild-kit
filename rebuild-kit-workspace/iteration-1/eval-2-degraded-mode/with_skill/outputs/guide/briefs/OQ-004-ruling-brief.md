# Ruling needed: OQ-004 — X-Internal-Bypass header: keep or kill?

**What's being decided.** Anyone sending `X-Internal-Bypass: 1` skips the reset rate limit
(ticketd/app/server.py:84 — comment: "undocumented bypass header"). Unauthenticated. Does an
internal tool depend on it, or is it a contractor leftover?

**Why it's ambiguous.**
- Reading A: deliberate escape hatch for an internal tool (it was written on purpose, exact
  match).
- Reading B: debugging backdoor that never got removed (undocumented, referenced nowhere
  else, no auth).

**Where it bites.** Flow guide/flows/password-reset.md; reset rate limiting only. Blocks
nothing: WO-006 implements parity behind config flag RESET_RATE_LIMIT_BYPASS_ENABLED
(default ON so replay passes). Flags the M2 gate.

**Options & consequences.**
1. Kill → flip the flag default at the M2 gate + add an ED entry for the bypass trace
   (reset-request-005-bypass would then expect 429). One-line change, closes a trivially
   exploitable bypass.
2. Keep → name the tool that uses it; consider authenticating it later (separate ruling).
3. Defer → parity ships; the bypass remains as exploitable as it is today (no worse).

**Recommendation (non-binding).** Kill at M2 unless a tool is named — an unauthenticated
bypass with no known consumer is pure liability.

---
Ruling: ____________  Ruled by: ________  Date: ______
