# The Generator/Executor Contract

This file defines every machine-readable artifact in the rewrite root. The generator writes them;
the executor validates against them. Deviating from these schemas breaks the only interface the
two sessions share — treat field names as API.

## Table of Contents

1. [rebuild.json — the layout block](#rebuildjson)
2. [ledger.json — machine state](#ledgerjson)
3. [Work order schema](#work-order-schema)
4. [Fidelity taxonomy](#fidelity-taxonomy)
5. [Problem brief entries](#problem-brief-entries)
6. [diff-rules.yaml](#diff-rulesyaml)
7. [expected-divergences.yaml](#expected-divergencesyaml)
8. [Input tiers](#input-tiers)
9. [Full root layout](#full-root-layout)
10. [Risk score](#risk-score)

## rebuild.json

Makes the structure declarative rather than assumed. Its presence is the resume signal: a skill
session that finds `rebuild.json` routes to resume/spec-patch mode instead of scaffolding.

```json
{
  "skill_version": "1.0",
  "created": "2026-08-08",
  "layout": {
    "legacy_dir": "legacy",
    "modern_dir": "modern"
  },
  "legacy_ref": "<full SHA the legacy tree is pinned at>",
  "legacy_pin_method": "submodule | sha-recorded-clone",
  "target_stack": {
    "language": "…", "framework": "…", "database": "…",
    "decided_by": "human | pending",
    "rationale": "one line, or PB citation"
  },
  "evidence": {
    "runtime_ingestion": "active | inactive",
    "data_census": "active | inactive",
    "trace_capture_t1": "active | inactive",
    "notes": "what evidence was provided; what degraded-mode caps apply"
  },
  "status": "generating | generated | executing",
  "phases_complete": ["P0", "P1"]
}
```

Real repo names work fine for `legacy_dir`/`modern_dir` (e.g. an existing checkout named
`acme-api/`); every script and doc resolves paths through this block — never hardcode `legacy/`.

## ledger.json

The single source of truth for execution state. Workflows read and write it; the orchestration
layer holds no state of its own that matters.

```json
{
  "milestones": [
    {"id": "M0", "name": "walking skeleton", "status": "pending | in_progress | complete",
     "gate": true, "approved_by": null, "approved_at": null}
  ],
  "work_orders": [
    {
      "id": "WO-014",
      "status": "pending | in_progress | blocked | awaiting_ruling | done",
      "milestone": "M2",
      "depends_on": ["WO-003", "WO-007"],
      "blocked_by_asks": ["OQ-007"],
      "verification": {"l1": null, "l2": "pass | fail | null", "l3": "pass | fail | null",
                        "last_run": null},
      "free_choices": [{"choice": "…", "rationale": "…"}],
      "gate": false, "gate_approved_by": null
    }
  ],
  "audit": {"claims_confirmed_pct": null, "branch_coverage_pct": null,
             "problem_coverage_pct": null, "demotion_rate": null}
}
```

## Work order schema

Work orders are the unit of execution: self-contained, dependency-declared, sized to a stated
context budget so the executor loads only the order plus its linked contracts. One file each:
`docs/features/WO-<nnn>-<slug>.md` with YAML frontmatter + body.

```markdown
# docs/features/WO-014-password-reset.md
id: WO-014            depends_on: [WO-003, WO-007]     milestone: M2
risk: 0.62 (inferred-claim ratio 0.3, complexity high, legacy coverage none)
usage_weight: 0.041   pain_weight: 0.18   context_budget: ~350 lines   gate: false

behaviors:
  - statement: Reset tokens expire after 30 minutes; expired tokens return
      the SAME error body as invalid tokens (deliberate non-disclosure).
    fidelity: FIXED
    evidence: [legacy/src/auth/reset.ts:88-114, trace: replay/traces/auth-041.jsonl]
  - statement: Reset email is sent synchronously in-request; times out under
      provider latency spikes (PB-012, severity high).
    fidelity: REPAIR — target: enqueue via transactional outbox (ruled OQ-003)
    evidence: [legacy/src/auth/reset.ts:131-140, trace: auth-017]   divergence: ED-012
  - statement: Token storage mechanism (currently MD5 in a legacy table).
    fidelity: FREE — outcome required (single-use, expiring); mechanism open.
  - statement: Rate limit of 3 requests/hour appears in code but a bypass
      header is honored in legacy/src/middleware/rl.ts:41. Intent unclear.
    fidelity: ASK — open-questions.md#OQ-007 (blocks: none; flags gate review)

acceptance:
  replay_set: auth-reset-*.jsonl (14 traces; ED-012 applies)
  tests: characterization/auth/reset.spec.ts
escalation: consult legacy/src/auth/reset.ts:60-140 only if spec ambiguity found
```

Every behavior line: `statement`, `fidelity`, `evidence` (except FREE, which carries a rationale
note), and `divergence:` linking REPAIRs to the manifest.

## Fidelity taxonomy

| Tag | Meaning | Evidence bar | Executor behavior |
|---|---|---|---|
| `FIXED` | Behavior must match legacy observably | Source citation **and** trace or characterization coverage | Implement exactly; any deviation fails verification |
| `REPAIR` | Legacy behavior is real and evidenced, but designated for correction | Evidence of current behavior **plus** a PB citation; target behavior ratified by the brief or an ASK ruling | Implement the target behavior; verified against the expected-divergence entry, not trace match |
| `FREE` | Outcome required; mechanism open | Rationale note for why fidelity is not required | Choose the idiomatic target-stack approach per `modern/CLAUDE.md`; record the choice in ledger notes |
| `ASK` | Ambiguous, conflicting, or inferred-only | The conflict itself, with citations for each reading | Never guess. Log to `open-questions.md`, block dependents, continue elsewhere |

## Problem brief entries

`docs/problem-brief.md` holds a register of entries:

```markdown
## PB-012 — Reset email blocks the request thread
- kind: defect | pain | grievance | goal | non-goal
- severity: high | medium | low
- reported_by: <name/role>          affected_area: auth/reset
- reproduction: (defects) steps or trace reference
- disposition: REPAIR in WO-014 | do-not-port | NFR target | out-of-scope (ruled …) | UNDISPOSITIONED
```

Human testimony is the third evidence class alongside source citations and traces — citable from
any artifact as `PB-nnn`. **Every PB entry must end the pipeline dispositioned; undispositioned
entries block workspace assembly** (checked in P9).

Open questions in `docs/open-questions.md` follow the same register pattern with `OQ-nnn` IDs,
each entry recording: the question, the conflicting readings with citations, which WOs it blocks,
and space for the eventual ruling + who ruled. PB *proposals* (executor believes an unsanctioned
legacy behavior is wrong) also land here — the executor never builds unsanctioned fixes.

## diff-rules.yaml

Normalization applied to both sides before diffing (`verification/replay/diff-rules.yaml`):

```yaml
normalize:
  - path: "$.**.updated_at"        # JSONPath — replace with placeholder
    rule: timestamp
  - path: "$.**.id"
    rule: uuid                      # any UUID → <UUID>
  - path: "$.items"
    rule: sort_by:sku               # order-insensitive arrays
  - header: "Date"
    rule: drop
ignore_headers: [X-Request-Id, Server]
state_diff:                         # post-run state comparison
  db_dump: {exclude_tables: [sessions, audit_log], exclude_columns: {users: [last_seen]}}
```

## expected-divergences.yaml

The authoritative changelog of every intentional behavior change. Human-signed.

```yaml
- id: ED-012
  pb: PB-012
  wo: WO-014
  match:
    trace_pattern: "auth-reset-*"
    field: "$.email_dispatch.mode"
  legacy: "sync"
  expected: "queued"
  ruled_by: <human>   ruled_at: <date>
```

The differ passes these entries only when they diverge **as specified**; any divergence not in
the manifest remains a failure.

## Input tiers

- **T1** — captured production traffic (highest realism; optional, never assumed).
- **T2** — the workhorse: scripted sessions and generated input sets driven through the twin-boot
  harness; legacy golden outputs recorded once per input set and cached (the pin makes the cache
  valid indefinitely), so the inner loop boots only `modern/`.
- **T3** — statically derived request/response pairs, marked provisional; T3-only evidence counts
  toward L2, never L3, and is flagged in the ledger.

**Per-WO acceptance bar:** 100% of the assigned replay set within diff rules — expected
divergences diverging as specified — plus all characterization tests green.

## Full root layout

```
rewrite-root/
├── CLAUDE.md                    # root contract (template: templates/root-claude-md.md)
├── rebuild.json
├── backlog.md                   # milestones M0..Mn, ordered work orders
├── ledger.json
├── docs/
│   ├── 00-overview.md           # system map, subsystem boundaries
│   ├── problem-brief.md         # PB-nnn register
│   ├── domain/                  # entities, invariants, glossary
│   ├── features/WO-*.md         # self-contained work orders
│   ├── contracts/               # openapi.yaml, schemas/, ddl.sql, fixtures/
│   ├── migration/               # mapping.md, census.md, reconciliation.sql
│   ├── do-not-port.md           # negative space, each entry with evidence
│   └── open-questions.md        # OQ register + PB proposals
├── verification/
│   ├── replay/                  # traces/*.jsonl, diff-rules.yaml, expected-divergences.yaml
│   ├── characterization/        # generated tests + golden fixtures
│   └── harness/                 # run-legacy.sh, run-modern.sh, diff-run.sh (twin-boot)
├── audit/                       # discrepancy report, coverage metrics
├── workflows/                   # orchestration scripts for this rewrite
├── guide/                       # generated field guide (see phases/P10-field-guide.md)
├── legacy/                      # READ-ONLY, pinned at legacy_ref
└── modern/                      # sole write target; own CLAUDE.md
```

## Risk score

Each WO's `risk` is a function of: inferred-claim ratio (claims without trace coverage),
ASK density, problem-brief severity touching its area, cyclomatic complexity, legacy test
coverage, churn history, and audit findings. Record the contributing factors inline (see the
WO example). Above threshold (default 0.5), set `gate: true` — the executor must halt for human
review before the WO can close.
