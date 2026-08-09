id: WO-001            depends_on: [WO-000]              milestone: M1
risk: 0.55 (PB-001 severity high, touches two call sites across two subsystems, FREE mechanism
  choice with a durability requirement, zero legacy test coverage to lean on)
usage_weight: 0.069 (close 4.95% + reset-request 1.95%, combined -- see usage-weights.json)
pain_weight: 0.9 (this WO exists because of a production outage, PB-001)   context_budget: ~300 lines
gate: true

## Why this WO exists

The June 2026 SMTP outage took ticket-closing down for ~40 minutes because notification email was
sent synchronously inside the request (`ticketd/app/server.py:76,94`). This is THE reason
leadership approved this rewrite (`docs/problem-brief.md`, Motivation). This WO builds the
decoupled dispatch mechanism; WO-002 (close) and WO-004 (reset) are its callers.

## Reading list

- `docs/problem-brief.md` — PB-001 in full.
- `docs/features/draft/notifications.md` — full behavioral extraction of `send_mail`.
- `docs/domain/reset_token.md` and `docs/domain/tickets.md` — just the sections on notification
  ordering (commit-then-send).
- `verification/replay/traces/tickets-close.jsonl` (trace `close-first-transition-001`) and
  `verification/replay/traces/auth-reset.jsonl` (trace `reset-request-001`) — both carry a
  `side_effects.notification` block from real legacy execution.
- `verification/replay/expected-divergences.yaml` — ED-001, ED-001b (this WO's acceptance target).

## Behaviors

- statement: No caller of notification dispatch may block on delivery. The HTTP response for
    `close_ticket` and `request_reset` must return without waiting on SMTP (or whatever the new
    delivery mechanism is) to complete.
  fidelity: REPAIR — target: async dispatch (queue, outbox table, or framework-native background
    task — FREE, record the choice). See `docs/problem-brief.md` PB-001, ED-001/ED-001b.
  evidence: [ticketd/app/notify.py:1-7, ticketd/app/server.py:67-76, ticketd/app/server.py:80-95,
    trace: close-first-transition-001 (dispatch_mode: "sync"), trace: reset-request-001
    (dispatch_mode: "sync"); traced perf evidence in perf-envelopes.json shows close/reset p50s
    running 4-5x the non-mail-sending routes even under healthy same-day conditions]
- statement: The underlying business transaction (ticket status change; reset-token row insert)
    must remain durable independent of notification delivery outcome — this was ALREADY true in
    legacy (commit happens before send at both call sites, `server.py:72` before `:76`,
    `server.py:93` before `:94`) and must not regress.
  fidelity: FIXED (preserve this ordering property) as a REQUIREMENT on the REPAIR design, not a
    separate behavior — the new async mechanism must not make the DB write depend on successful
    enqueue in a way that could roll back a otherwise-successful business transaction.
  evidence: [ticketd/app/server.py:69-76, :90-95]
- statement: Unlike legacy (fire-and-forget past the `send_mail()` call, no crash recovery), the
    new mechanism must be **durable across a process crash between commit and dispatch** — a
    crash in that window currently silently drops the legacy notification forever; the target
    behavior should not have that gap (an outbox table polled by a worker, or an equivalent durable
    queue, not a bare in-process background task that dies with the process).
  fidelity: REPAIR (this is new ground — legacy has no durability story here at all — but it's a
    reasonable reading of "the business transaction succeeds independent of notification delivery"
    combined with PB-001's intent; it is not separately PB-cited beyond PB-001 itself). FREE on
    exact mechanism.
  evidence: [ticketd/app/notify.py:1-7 — no retry/persistence exists at all today; this is an
    absence, not a cited positive behavior, so treat this bullet's fidelity claim as somewhat
    inferred — if in doubt about scope, the minimum bar is "no worse than legacy" (fire-and-forget
    is acceptable) and the durability improvement is a stretch goal, not a hard gate]
- statement: Recipient address, sender address, and message body content are unchanged from
    legacy (`watchers@example.internal` for close; the requester's submitted email + raw token in
    plaintext for reset).
  fidelity: FIXED — only the dispatch mechanism (sync -> async) is REPAIR; content is not.
  evidence: [ticketd/app/server.py:76,94, ticketd/app/notify.py:7]

## Acceptance

- L1: n/a (not a route-level contract change — the HTTP contract for `close`/`reset` is unchanged
  by this WO; see WO-002/WO-004 for their own L1).
- L2: a test asserting the ticket-close / reset-request HTTP response returns before any
  dispatch-completion signal (e.g. mock the delivery mechanism with an artificial delay and assert
  response latency is independent of it) — this is the direct regression test for PB-001 and
  should be written against a fake/slow backend the way legacy was reproduced via `fake_smtp.py`.
- L3: `verification/harness/diff-run.sh tickets-close` and `diff-run.sh auth-reset` — per
  `verification/README.md`'s documented gap, `drive_trace.py` cannot observe `side_effects` over
  HTTP today. **This WO must close that gap**: expose a test-only introspection point (e.g. a
  `/internal/test/last-dispatch` endpoint gated to test config, or have the harness read the
  outbox/queue table directly) so `diff-run.sh` can actually verify ED-001/ED-001b rather than
  silently passing through unchecked `side_effects` data. Until this is done, L3 for this WO's
  core claim is NOT actually verified regardless of what the harness reports — treat that as this
  WO's own acceptance criterion, not an optional nice-to-have.
- gate: **true** — PB-001 is the reason this whole rewrite exists; a human should confirm the
  chosen mechanism (queue vs. outbox vs. BackgroundTasks) and its durability story before this
  closes. `expected-divergences.yaml`'s ED-001/ED-001b are UNSIGNED (see that file's header) —
  getting them signed is part of this gate.

## Escalation

Consult `ticketd/app/notify.py` (whole file, it's 7 lines) and `ticketd/app/server.py:67-95` if the
draft spec / traces leave the exact ordering or content unclear. Do not read the rest of
`server.py`.
