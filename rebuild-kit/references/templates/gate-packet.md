# Template: guide/briefs/WO-nnn-gate-packet.md

Emitted when a gate WO halts. Purpose: the human signing understands what they're signing.

```markdown
# Gate review: WO-014 — <title>

**What this work order does.** <2-3 sentences, domain language.>

**Why it's gated.** risk: 0.62 — drivers: <inferred-claim ratio 0.3 / complexity high /
PB-012 severity high / no legacy test coverage — the actual factors, not the formula>

**What was built.** <summary of the implementation + FREE choices made, from ledger notes>

**What to inspect.**
- Verification: L1 <pass>, L2 <pass, N tests>, L3 <replay set, N traces, divergences: ED-012
  diverged as specified>
- Spot-check suggestions: <the 2-3 highest-risk behaviors, with trace links to eyeball>
- Open items in this area: <OQ refs>

**Relevant traces.** <links into verification/replay/traces/ with one-line annotations>

---
Approve: ____  Reject (reason → open-questions.md): ____  Approver: ____  Date: ____
```
