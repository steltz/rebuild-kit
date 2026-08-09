# Ruling needed: OQ-002 — What consumes a confirmed password reset?

**What's being decided.** Whether the reset flow serves an external system (and must be
kept exactly) or is vestigial (and could be dropped or simplified in a later ruling).

**Why it's ambiguous.**
- Reading A: an external auth system calls confirm and uses the returned email — evidence:
  confirm's only output is `{"ok": true, "email": ...}` (ticketd/app/server.py:108), yet no
  login endpoint or password storage exists anywhere in ticketd.
- Reading B: vestigial — `users` is touched by no code path; reset never validates the email
  against anything.

**Where it bites.** Flow guide/flows/password-reset.md. Blocks nothing (WO-006 implements
observed behavior either way) but frames the M2 gate: if vestigial, you may cancel WO-006
outright and save the riskiest WO in the backlog.

**Options & consequences.**
1. External consumer exists → name it; WO-006 proceeds as specced; consider adding it to the
   integration notes.
2. Vestigial → cancel WO-006 + drop reset_tokens from migration (large simplification), or
   keep as-is consciously.
3. Defer → WO-006 builds to observed behavior; possible wasted effort if later ruled vestigial.

**Recommendation (non-binding).** Answer before M2 starts; this is the single
highest-leverage ruling in the backlog.

---
Ruling: ____________  Ruled by: ________  Date: ______
