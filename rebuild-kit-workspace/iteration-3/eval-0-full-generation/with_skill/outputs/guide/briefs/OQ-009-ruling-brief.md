# Ruling needed: OQ-009 — What timezone did the legacy server run `datetime.now()` in?

**What's being decided.** A pure factual gap, not a design choice: nothing in the supplied
evidence (README, code, access log) states what timezone the production ticketd server's clock
was set to. This blocks correctly converting existing `created_at`/`closed_at` data if OQ-006 is
ruled toward UTC-aware storage.

**Why it's ambiguous.** It's not ambiguous — it's simply unanswered. No reading conflict exists
here; someone with operational knowledge of the deployment just needs to say what it was (or
confirm it was always UTC, in which case this resolves trivially).

**Where it bites.** Blocks: WO-005's migration transform for `created_at`/`closed_at` specifically
— nothing else. Everything else in WO-005 (tickets/users row migration, reset_tokens policy) can
proceed independently of this answer.

**Options & consequences.** Not applicable in the usual sense — this needs an answer, not a
choice between tradeoffs. If truly unknowable (server long decommissioned, nobody remembers),
the fallback is to treat existing timestamps as ambiguous/best-effort and document that
explicitly in the migration record rather than silently guessing UTC or any other zone.

**Recommendation (non-binding).** Check deployment/ops documentation or infrastructure-as-code
history before assuming this is unanswerable — it's the kind of fact that's often recorded
somewhere (a systemd unit's `Environment=TZ=`, a Docker base image, a cloud region default) even
when nobody remembers it off the top of their head.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
