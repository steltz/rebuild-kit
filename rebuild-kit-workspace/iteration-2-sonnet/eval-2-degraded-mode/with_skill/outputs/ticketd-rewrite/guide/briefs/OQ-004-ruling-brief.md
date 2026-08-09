# Ruling needed: OQ-004 — Is the absence of any auth/session layer on the Tickets API intentional?

**What's being decided.** Every route in ticketd — listing, creating, and closing tickets;
requesting a password reset; exporting all tickets as CSV — is reachable with no credential, no
session, no API key. Should the FastAPI rewrite preserve that, or is this a gap that should be
closed?

**Why it's ambiguous.**
- Reading A: intentional. "Internal ticket tracker" plausibly sits behind a network perimeter
  (VPN, internal load balancer, reverse-proxy auth) that this codebase simply isn't responsible
  for — plenty of internal tools are built this way deliberately. No evidence either confirms or
  denies this; nothing in the handover mentions a perimeter.
- Reading B: a real gap. The password-reset flow's mere existence implies *some* notion of user
  identity matters enough to protect — evidence: `legacy/app/server.py:80-108`. Yet nothing
  gates any route behind it. Evidence: full read of `legacy/app/server.py`, zero
  `@login_required`-equivalent decorators, zero session/cookie/token checks anywhere.

**Where it bites.** Affected flows: all of them — `guide/legacy/tickets.md`,
`guide/legacy/auth-password-reset.md`, `guide/legacy/admin-export.md` all note this. Blocks:
nothing directly (no WO in the current backlog adds auth — none was requested), but it flags
gate review broadly, because the FastAPI rewrite could easily and *accidentally* add auth
middleware as a "obviously good practice" default, which would itself be an unsanctioned
behavior change in the other direction. Usage: unknown (no runtime evidence this run).

**Options & consequences.**
1. **Rule "intentional, perimeter-protected."** No auth gets added; this OQ closes, no PB entry
   needed. Fastest path; risk is silent if the perimeter assumption turns out to be wrong.
2. **Rule "it's a gap, add auth."** Requires a new PB entry (this is currently unreported, so
   it's a new goal, not a REPAIR of a named defect) and a real design decision — session-based?
   API key? SSO? — none of which this workspace has evidence to recommend. Would need its own
   intake round.
3. **Defer.** Ship the rewrite with the same no-auth posture as today (safest faithful-port
   default) and revisit once real usage/deployment context is known. This is the recommendation
   below.

**Recommendation (non-binding).** Defer (option 3) — porting "no auth" faithfully is zero-risk
today (it changes nothing observable) and reversible later; adding auth without a clear model in
mind risks guessing wrong on session mechanism, scope, and UX. If the perimeter assumption
(reading A) is actually correct, deferring costs nothing. If it's wrong (reading B), that's a
genuinely new project, not a rewrite detail, and deserves its own conversation.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
