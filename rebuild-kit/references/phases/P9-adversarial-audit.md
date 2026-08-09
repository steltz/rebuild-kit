# P9 — Adversarial Audit

Outputs: `audit/` — discrepancy report + coverage metrics. Workspace assembly is **blocked**
until the audit passes its own bar.

The executor will trust the docs completely, so the docs must earn it. The audit's independence
is structural: fresh-context auditors are given **only** the legacy tree, the problem brief, and
the draft specs — none of the generator's reasoning, notes, or drafts-in-progress. If you are
running serially without subagents, approximate this: audit from the artifacts alone, re-deriving
from source, never from memory of writing the spec.

## Four procedures, per P3 module/subsystem

1. **Falsification.** For every `FIXED` claim, attempt to construct a counterexample from
   source: an input, flag state, or code path under which the claimed behavior does not hold.
2. **Coverage hunt.** Enumerate branches, feature flags, and error paths present in source but
   represented in no spec; each becomes a new spec item or a do-not-port candidate.
3. **Fixture spot-check.** Validate sampled golden fixtures against both the contracts and the
   source logic.
4. **Problem coverage.** Verify every PB entry holds a disposition — a REPAIR behavior in some
   WO, a do-not-port entry, an NFR target, or an explicit out-of-scope ruling.
   Undispositioned entries block assembly.

## Verdicts and consequences

Per claim: `confirmed | contradicted | unverifiable`. Contradicted and unverifiable claims are
**demoted to ASK automatically** — the spec is edited, the OQ register grows, affected WO risk
scores update. No arguing with the auditor in the artifacts; a disputed verdict is itself an ASK.

## Metrics — ship them with the report

`audit/metrics.json` + human-readable report: % claims confirmed, spec branch coverage,
problem coverage, demotion rate, per-module table. These land in `ledger.json.audit` so the
humans signing gates know how hard the docs were attacked and how they held up.

## Workflow shape

Independent adversaries per claim cluster + dedicated branch-coverage hunters, every subagent
starting clean. Audit depth stops depending on app size because coverage is enumerated from the
inventory. Serial fallback: audit module-by-module in separate passes, falsification first.
