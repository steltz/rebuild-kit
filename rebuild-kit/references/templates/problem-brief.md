# Template: docs/problem-brief.md

```markdown
# Problem Brief — <system name>
<!-- Captured <date> from <who>. Human testimony: third evidence class alongside code + traces.
     Every entry must end the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation
<why rewrite, why now — prose, cite PB entries below where specific>

## Register

### PB-001 — <one-line title>
- kind: defect | pain | grievance | goal | non-goal
- severity: high | medium | low
- reported_by: <name/role>          affected_area: <subsystem/path>
- detail: <what happens / what's wanted>
- reproduction: <steps, trace ref, or issue link — required for defects>
- disposition: UNDISPOSITIONED
  <!-- becomes: REPAIR in WO-nnn | do-not-port | NFR target | out-of-scope (ruled by <who>, <date>) -->

<!-- ...PB-002 etc. Sections below are views over the register, not separate content. -->

## NFR targets
<measurable goals promoted from `goal` entries: SLOs, scale, operability — with PB IDs>

## Non-goals
<explicit out-of-scope list, with PB IDs>

## Open intake questions
<gaps the interview could not fill — non-interactive runs record them here rather than inventing>
```
