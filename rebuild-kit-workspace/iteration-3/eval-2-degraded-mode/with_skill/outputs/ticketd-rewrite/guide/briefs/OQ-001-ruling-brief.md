# Ruling needed: OQ-001 — Does `X-Internal-Bypass: 1` need to survive the rewrite?

**What's being decided.** The legacy password-reset request endpoint skips its per-email rate
limit (3/hour) whenever the caller sends the header `X-Internal-Bypass: 1` — no other check
gates it. Should the rewrite keep this escape hatch, and if so, behind real authentication?

**Why it's ambiguous.**
- Reading A: It's a deliberate internal-tooling escape hatch (support staff, automated tests) —
  keep it, but move it behind an actual authenticated/internal-only mechanism instead of a bare
  header anyone can send. evidence: `legacy/app/server.py:84`
- Reading B: It's leftover debug scaffolding that shouldn't exist in a security-sensitive
  rate-limit path — drop it entirely. evidence: same line; the code's own comment calls it
  "undocumented"; nothing else in the tree references or explains it.

**Where it bites.** Affected flow: `guide/flows/password-reset.md` (the request step). Blocks:
`WO-003` — the whole auth-reset work order is `awaiting_ruling` on this question, not just the
bypass behavior itself, since implementing the rate limit at all means deciding what to do with
this branch. Usage: unknown — no access logs exist to show whether this header is ever sent in
production (`docs/problem-brief.md` OQ-INTAKE-02).

**Options & consequences.**
1. Keep it, gated by real auth (e.g. a service-to-service credential) → preserves an operational
   capability if one genuinely exists, but adds new surface (an auth mechanism that doesn't
   exist anywhere else in this app) for a capability nobody has confirmed is used.
2. Drop it entirely → simpler, closes an unauthenticated rate-limit bypass, but breaks whatever
   (if anything) currently relies on it, silently, with no way to detect that from this codebase
   alone.
3. Defer → `WO-003` stays `awaiting_ruling`; M1 cannot fully close until this is resolved.

**Recommendation (non-binding).** The evidence leans toward reading B (drop): there's no
authentication protecting the header today, no documentation, no other reference anywhere in the
tree, and "undocumented" is the code's own word for it. But this is exactly the kind of judgment
call that benefits from someone who knows the operational history the code doesn't show — this
recommendation is a starting point, not a substitute for that context.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
