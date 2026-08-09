## Summary

I generated a complete rewrite workspace at `/private/tmp/wsvc-9f7cb54bfb/ticketd-rewrite/` for the `ticketd` legacy app (found at `ticketd-nohistory/`, not `./ticketd` as you referenced — noted for your awareness), using the rebuild-kit skill's full 11-phase pipeline, running non-interactively per your instructions. 12 commits, clean tree, `rebuild.json.status: "generated"`.

**What's real, not just scaffolded:**
- **Legacy actually boots.** I installed Flask in a throwaway venv, ran it via Flask's test client, and confirmed all 7 routes behave exactly as documented — including reproducing an unhandled 500 when SMTP is unreachable, live evidence for PB-001.
- **The twin-boot harness works end-to-end.** 19 real captured traces (not hand-written fixtures) from booting legacy, a determinism baseline (12/12, 7/7 pass legacy-vs-itself), and `diff-run.sh` correctly reports "0/19, missing on modern side" pre-M0 — failing loudly and honestly rather than passing on nothing.
- **Independent adversarial audit.** A fresh-context subagent, given only the legacy source and problem brief (not my drafts), independently confirmed all 15 sampled behavioral claims and found 8 genuinely new gaps — including two undocumented crash paths (invalid `priority`, non-string `title` both cause raw 500s). Those became `OQ-005`/`OQ-006` and got folded into `WO-001`, not silently fixed.
- **6 work orders, 3 milestones**, both problem-brief entries (PB-001 sync email, PB-002 MD5 tokens) dispositioned as REPAIR, gated appropriately given zero ratified rulings.
- **6 ruling briefs** in `guide/briefs/` — one per open question, with readings, evidence, and a non-binding recommendation, so whoever answers them later doesn't have to re-open the legacy tree.

**Real limitations, stated plainly:**
- No runtime evidence, no data census, no T1 production traces — everything's marked degraded/inactive in `rebuild.json.evidence`, and P8 backlog ordering falls back to severity, not usage.
- All expected-divergence entries are **unratified** — no human was available to sign them.
- `WO-005` (migration) and `WO-006` (CSV export) are blocked on production DB access and an OQ ruling respectively.
- I made one unrequested but load-bearing infrastructure call: vendored a copy of `replay.py` into `verification/harness/` so the harness runs standalone for a later executor session with no skill installed — the alternative (depending on the skill's external path) would silently break at execution time.

Open the root fresh in a new session (no skill needed) and `WO-001` is ready to implement today — it's the only ungated, fully-unblocked item.