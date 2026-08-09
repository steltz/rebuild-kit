# P4 — Behavioral Extraction

Outputs: draft feature specs — the raw material P8 cuts into work orders. Store as
`docs/features/draft/<subsystem>-<feature>.md` until P8 reshapes them.

Per feature: the behavior rules, edge cases, and error paths as the code actually implements
them — every claim cited, confidence-tagged, and fidelity-tagged per `references/schema.md`.

## Procedure (per feature, enumerated from P3 subsystem membership)

1. **Trace the happy path** from route/entrypoint to response: inputs accepted, validations,
   state changes, side effects (emails, events, external calls), response shape.
2. **Mine the edges**: every branch is a potential behavior. Boundary values, empty/null
   handling, concurrency guards, retries, idempotency, pagination quirks, timezone handling.
3. **Error paths deserve equal rigor** — error bodies, status codes, and partial-failure
   behavior are load-bearing (clients depend on them). Note where errors deliberately hide
   information (same body for distinct causes) — that's usually intentional.
4. **Tag every statement**:
   - matches a PB defect entry → `REPAIR` with the PB citation and target behavior (from the
     brief, or `ASK` if the brief names the problem but not the fix)
   - implementation detail where only the outcome matters → `FREE` with rationale
   - code says two things, or the behavior is inferred without a trace → `ASK`, log to
     `open-questions.md` with both readings cited
   - everything else observed and citable → `FIXED`
5. **Confidence**: mark claims `cited` (file:line), `traced` (also has runtime evidence), or
   `inferred` (deduced, no direct site) — inferred claims are P9's first targets and count
   toward the WO risk score.

## Workflow shape

This is the fan-out-heaviest phase: one subagent per feature, **paired extract-and-verify** —
a second agent independently confirms each claim against source before it enters the draft spec.
Claims that fail pair-verification become ASKs, not silent edits. Serial fallback: extract then
self-verify in a separate pass over each spec, reading only the citations, not your notes.

## Discipline

- Don't paraphrase code into vagueness. "Validates the email" is not a behavior;
  "rejects addresses failing RFC-lite regex at reset.ts:23 with 422 `{error:'invalid_email'}`" is.
- Workarounds and oddities get documented, not cleaned up — cleanup is a REPAIR/FREE decision,
  and it isn't yours unless the brief sanctions it. When you believe an unsanctioned behavior is
  wrong, file a PB proposal to `open-questions.md`; never quietly fix it in the spec.
