# Orchestration workflows — empty, deliberately

The skill's "Orchestration — dynamic workflows" section fans out heavy phases (P1/P3-P5
extraction, P9 audit, P10 render) across parallel fresh-context subagents on large targets.
ticketd is not a large target: 5 legacy source files, 169 lines of code, 7 routes, 10 work
orders. Every extraction phase in this generation ran serially in one session; the single P9
adversarial audit ran as one dispatched fresh-context subagent (see `audit/report.md`'s
header), not a multi-agent fan-out, because one subsystem-sized audit was enough to cover the
whole app in one pass.

"Proportionality is a design rule" (SKILL.md) — workflows exist for when scale, not judgment,
is the constraint. Nothing here needed one. If a future spec-patch or a much larger legacy
addition changes that calculus, a real orchestration script belongs in this directory,
versioned and reviewed like code — not before.
