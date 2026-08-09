# Ruling needed: OQ-002 — Is `X-Internal-Bypass` a sanctioned escape hatch or dead scaffolding?

**What's being decided.** A request header, `X-Internal-Bypass: 1`, completely skips the 3/hour
rate limit on password-reset requests. It's real (confirmed by directly booting legacy and
sending it, trace `reset-request-bypass-header-006`), completely undocumented anywhere in the
codebase or README, and nobody currently knows why it exists.

**Why it's ambiguous.** Reading A: a legitimate internal-service allowance — it only touches the
rate-limit branch, not token minting itself, which is at least *consistent* with deliberate,
scoped design (`ticketd/app/server.py:84`). Reading B: forgotten debug/test scaffolding — nothing
documents it, and the supplied access-log sample gives no evidence either way (it doesn't capture
custom headers, so absence-of-evidence here isn't evidence-of-absence).

**Where it bites.** Affected flow: password reset request (`guide/flows/password-reset.md`).
Blocks: WO-004 cannot close — it ships with everything else about the reset-request endpoint
built and tested, but this one code path deliberately left unimplemented (neither preserved nor
removed) pending this ruling. Usage: reset-request is 1.95% of sampled traffic — low volume, but
this is a security-adjacent question, not a traffic-driven one.

**Options & consequences.**
1. **Preserve it**, undocumented header and all → carries a possible backdoor forward into a
   freshly-scrutinized system without ever having confirmed intent. Lowest engineering effort,
   least defensible from a security standpoint.
2. **Preserve it, but document and formalize it** (e.g. require a real internal-service API key
   instead of a magic header value) → keeps whatever legitimate use case might exist, closes the
   "nobody knows why" gap. Requires figuring out who, if anyone, actually needs this.
3. **Drop it entirely** → simplest, safest by default, but is itself an unsanctioned behavior
   change if some internal caller genuinely depends on it (nothing in the evidence available to
   this workspace can rule that out).

**Recommendation (non-binding).** This is exactly the kind of undocumented control nobody should
guess about. Before ruling, it's worth a quick internal check — ask around whether any internal
tooling, script, or service account has ever sent this header — since that answer alone might
resolve the ambiguity outright and turn this from a policy decision into a simple fact-check.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
