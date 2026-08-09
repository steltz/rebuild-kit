# Backlog — ticketd rewrite

Ordering: usage weight (static-proxy — no traffic data exists, see usage-weights.json) +
pain weight (PB severities), topologically constrained. Machine state lives in ledger.json;
this file is the human view.

## M0 — Walking skeleton  [GATE]
| WO | title | risk | gate | blocked by |
|---|---|---|---|---|
| WO-001 | FastAPI+Postgres skeleton, harness boot contract, list tickets | 0.55 | M0 gate | — |

Proves the stack and the twin-boot plumbing while a misread costs one WO. The M0 gate packet
also carries the two signature requests the owner owes the workspace:
**expected-divergences.yaml (ED-001..ED-004) is generator-drafted and unsigned**, and the
REPAIR targets (PB-001/PB-002) need ratification.

## M1 — Core tickets
| WO | title | risk | gate | blocked by |
|---|---|---|---|---|
| WO-003 | Create ticket (aliases, slug, ED-004a/b) | 0.35 | — | — |
| WO-002 | Get ticket (200-{} quirk) | 0.15 | — | — |
| WO-004 | Email dispatch subsystem (PB-001 mechanism) | 0.60 | design gate | — |
| WO-005 | Close ticket + watcher notification (ED-001) | 0.40 | — | WO-004 |

M1 close: full core replay set green except reset-*/export traces; guide refresh.

## M2 — Auth reset + long tail  [GATE]
| WO | title | risk | gate | blocked by |
|---|---|---|---|---|
| WO-006 | Password reset (ED-002/ED-003, OQ-004 flag) | 0.65 | M2 gate | WO-004 |
| WO-007 | Internal CSV export | 0.30 | — | **OQ-001 ruling** |

M2 gate doubles as the ruling session: OQ-001 (export dead?), OQ-002 (what consumes reset?),
OQ-004 (bypass header keep/kill). One conversation with the owner clears all three.

## M3 — Data migration & cutover  [GATE ×2]
| WO | title | risk | gate | blocked by |
|---|---|---|---|---|
| WO-008 | Migration tooling (transform + reconciliation) | 0.55 | — | — (buildable now) |
| WO-009 | Census, rehearsal, cutover | 0.75 | rehearsal + cutover | **OQ-INT-2 (prod DB access)** |

## Standing constraints
- Legacy tree read-only; every deviation needs a PB or ED entry; ASK → open-questions.md.
- Degraded-mode: usage weights are estimates; perf envelopes absent; census pending.
  When logs/DB arrive, run spec-patch (rebuild-kit resume mode) before trusting weights.
