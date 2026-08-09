# Workflows

Empty by design, not by omission. This rewrite root's legacy tree is 5 files / ~165 lines
(`hotspots.md`) — small enough that every generation phase (P0-P10) ran serially in one session
rather than as a fanned-out multi-agent workflow, per the rebuild-kit skill's own proportionality
rule ("Workflows exist for when scale, not judgment, is the constraint... on small targets, run
the pipeline serially" — SKILL.md).

If this workspace is later extended to cover a larger legacy surface (e.g. a spec-patch pulls in
a bigger adjacent system), and a phase's fan-out becomes worth the token cost, save that
orchestration script here, versioned like any other code in this root.
