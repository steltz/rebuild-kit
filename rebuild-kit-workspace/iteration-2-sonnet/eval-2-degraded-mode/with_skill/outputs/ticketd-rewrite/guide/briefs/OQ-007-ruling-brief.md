# Ruling needed: OQ-007 — Keep, document, or drop the `X-Internal-Bypass` reset-rate-limit bypass header?

**What's being decided.** `legacy/app/server.py:84`: sending header `X-Internal-Bypass: 1` on a
`POST /api/auth/reset` request skips the 3-requests/hour rate limit entirely. Should the rewrite
carry this forward?

**Why it's ambiguous.**
- Reading A: keep it (FIXED). It's real, evidenced, working code — some internal caller may
  depend on it today (an admin tool, a test harness, a support workflow). Removing it silently
  could break that caller with no warning. Evidence: `legacy/app/server.py:84`, one line, no
  surrounding comment.
- Reading B: it's an undocumented backdoor around the app's only abuse-protection mechanism, on
  its most security-sensitive endpoint (password reset). No docstring, no test, no PB entry, no
  README mention anywhere explains who's meant to send this header or why. Carrying it forward
  into a fresh build without a deliberate decision is precisely the "faithfully rebuild the
  cruft" failure mode the fidelity taxonomy (FIXED/REPAIR/FREE/ASK) exists to catch — this
  workspace's evidence-or-it-doesn't-ship principle means "it's real code" isn't the same as
  "it's meant to be there."

**Where it bites.** Affected flows: `guide/flows/password-reset.md` (step 1 — the request
route). Blocks: nothing in the current backlog — `WO-003` can implement everything else in the
auth-reset flow without this ruling. It only flags gate review for `WO-003`'s sign-off. Usage:
unknown (no runtime evidence this run — no way to tell if this header is ever actually sent by
anything).

**Options & consequences.**
1. **Keep as-is.** Port the header check exactly. Zero behavior change, zero risk of breaking an
   unseen caller. Leaves an undocumented security-relevant bypass in a fresh codebase, which a
   future security review will flag again — this ruling just defers that conversation, doesn't
   resolve it.
2. **Document it properly, keep the mechanism, tighten the value.** E.g. a real config-driven
   allowlist of trusted internal callers instead of a magic header value anyone could send if
   they guessed it (`X-Internal-Bypass: 1` is not a secret, it's a shared string) — but this
   changes an observable API contract (whatever "trusted" means now needs real enforcement), so
   it needs a PB entry to sanction it as REPAIR, not just a ruling.
3. **Drop it.** Any caller depending on it breaks. Only safe with confirmation that no such
   caller exists — which nothing in this workspace's evidence can currently provide (no logs).

**Recommendation (non-binding).** Option 1 (keep as-is) until real usage evidence exists. This
is a security-adjacent decision hiding inside what looks like a small config detail — the
generator's evidence bar (a real caller might depend on this) argues for a faithful port over a
guess, but this is exactly the kind of item worth a human's deliberate attention rather than
auto-approval, which is why it's flagged for gate review rather than silently defaulted.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
