id: WO-004            depends_on: [WO-001, WO-002]         milestone: M1
risk: 0.45 (inferred-claim ratio low; PB-001 severity high touches this WO but the mechanism
  risk was already absorbed by WO-002; complexity low; legacy coverage none)
usage_weight: 0.0495
pain_weight: 0.7 (this is the SECOND of PB-001's two call sites, and the one actually named in
  the June incident: "closing tickets was down for 40 minutes")
context_budget: ~250 lines (this WO + docs/features/draft/tickets-close.md + WO-002)
gate: false

## What this WO does
Implement `POST /api/tickets/{id}/close` using WO-002's async dispatch mechanism instead of a
synchronous SMTP call. This is the exact endpoint the June outage incident was about.

behaviors:
  - statement: "Only rows not already closed transition; response is always 200 {closed: bool}
      -- true only on an actual open->closed transition this call performed, false for both
      'already closed' and 'nonexistent id' (not distinguishable from the response)."
    fidelity: FIXED
    evidence: [legacy/app/server.py:67-77, docs/features/draft/tickets-close.md]
  - statement: "On a successful transition, a notification is sent to watchers@example.internal
      with body 'closed: {title}' -- via WO-002's async mechanism, not synchronously in-request."
    fidelity: REPAIR (dispatch mechanism) / FIXED (content, recipient, and the 'only on actual
      transition' guard -- no notification on an already-closed or nonexistent id)
    evidence: [legacy/app/server.py:73-76, docs/problem-brief.md PB-001]
    divergence: ED-001 (via WO-002)

acceptance:
  replay_set: tickets-close-*.jsonl (3 traces, captured T2 golden, self-check validated)
  tests: verification/characterization/test_against_golden.py, plus WO-002's async-dispatch
    test extended to cover this call site specifically (mail transport down => close still
    returns 200 promptly)
  l1: docs/contracts/openapi.yaml /api/tickets/{id}/close
  l3: verification/harness/diff-run.sh tickets-close

escalation: legacy/app/server.py:67-77 only.
