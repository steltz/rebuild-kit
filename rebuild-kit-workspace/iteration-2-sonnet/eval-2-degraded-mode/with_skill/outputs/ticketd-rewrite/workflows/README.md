# workflows/

Empty by design. The skill's proportionality rule: "Workflows consume far more tokens than a
plain session... Workflows exist for when scale, not judgment, is the constraint." ticketd is 5
legacy files, 165 lines, 7 routes — every generation phase in this workspace ran serially, in a
single session, and that was the right call, not a shortcut. If this codebase grows enough that
a future spec-patch run (or the executor's milestone-frontier parallelism, see root CLAUDE.md)
genuinely needs multi-agent fan-out, save the orchestration script here, versioned like any
other code — don't let it live only in a chat transcript.
