# P8 — Backlog Synthesis

Outputs: `backlog.md`, `ledger.json`, `docs/features/WO-*.md` (final work orders), root and
`modern/` CLAUDE.md completed with the executor loop.

## Procedure

1. **Cut specs into work orders.** Reshape P4 draft specs + P6 migration plan into WOs per the
   schema (`references/schema.md#work-order-schema`): self-contained, dependency-declared,
   sized to a stated context budget (~350 lines of linked reading is the norm). Migration WOs
   are ordinary WOs with reconciliation acceptance.
2. **Score risk** per WO from: inferred-claim ratio, ASK density, PB severity touching its
   area, complexity, legacy test coverage, churn (see schema.md#risk-score). Above threshold →
   `gate: true`.
3. **Order the backlog**: usage weight + pain weight first (effort follows usage and pain — the
   endpoints carrying the traffic and the defects motivating the rewrite ship first), subject
   to topological order on dependencies.
4. **Milestone 0 is always the walking skeleton**: one thin end-to-end slice of the highest-
   usage flow — entry, auth, one core action, persistence, response — running in `modern/` and
   passing the harness. It validates the stack choice, proves the twin-boot plumbing, and
   surfaces systemic spec misreads while they cost one WO instead of forty. Group the rest into
   milestones M1..Mn, each closing with a full-suite regression replay and human review of any
   new expected-divergence entries.
5. **Write the executor loop into root CLAUDE.md** (template has the skeleton): select highest-
   priority unblocked WO → load only it + linked contracts → implement in modern/ per fidelity
   tags (`legacy/` only at cited escalation pointers, never bulk reading) → run L1/L2 locally,
   L3 through the harness → green: ledger + commit; red on suspected spec bug: file to
   open-questions.md, set `awaiting_ruling`, never improvise → gates: stop, emit gate packet,
   await sign-off → milestone close: full regression + guide refresh.
6. **modern/CLAUDE.md**: target stack (human's choice from intake — if still `pending`, this
   blocks: get the ruling), conventions, architecture rules derived from the brief's goals.
7. **Problem-coverage check**: every PB entry must now hold a disposition. Any UNDISPOSITIONED
   entry: route it (REPAIR WO, do-not-port, NFR, or out-of-scope ASK) before P9.

## Parallel execution note (write into CLAUDE.md)

Between control points, milestone execution may run as a workflow: the ledger's dependency
graph schedules the unblocked frontier across worktree-isolated subagents; merges land only
through a green harness run; conflicts and cross-WO discoveries file to open-questions.md.
Parallelism changes throughput, never semantics — gates and open ASKs are hard boundaries.
