# Ruling needed: OQ-002 — `X-Internal-Bypass: 1`: keep or drop?

**What's being decided.** The reset-request rate limit (3/email/hour) can be skipped by
sending an undocumented header. The rewrite must know whether that's a feature or a hole.

**Why it's ambiguous.**
- Reading A — operational escape hatch: the check is explicit and deliberate-looking —
  evidence: `ticketd/app/server.py:84` `if request.headers.get("X-Internal-Bypass") != "1"`,
  comment "undocumented bypass header".
- Reading B — forgotten debug hook: no documentation, no auth around it; anyone who learns
  the header defeats the limit on a security-adjacent flow (the same table PB-002 flagged).

**Where it bites.** WO-005 (reset request, M2, gated) — implemented exactly as legacy until
ruled; replay freezes both the bypass (trace `auth-reset-req-005`) and its side effect
(bypassed requests still count toward later limits, trace `-007`). Usage: unknown — the
access log doesn't record headers; internal tooling may depend on it invisibly.

**Options & consequences.**
1. Keep as-is → whatever uses it keeps working; the hole ships to the new system too.
2. Drop → a divergence entry + removing the trace from acceptance; any internal tool using
   it starts getting 429s — grep internal tooling first.
3. Keep but authenticate/allowlist it → new behavior, needs a small PB amendment.

**Recommendation (non-binding).** Ask ops/tooling owners if anything sends this header.
If nothing does, drop it (option 2) — it's one manifest entry now.

---
Ruling: ____________  Ruled by: ________  Date: ______
