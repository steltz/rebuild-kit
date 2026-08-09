# Template: docs/open-questions.md

```markdown
# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md). -->

## OQ-001 — <one-line question>
- raised_by: generator P4 | audit P9 | executor WO-nnn
- kind: ambiguity | conflict | inferred-only | discrepancy | pb-proposal
- readings:
  - A: <reading> — evidence: <file:line / trace>
  - B: <reading> — evidence: <file:line / trace>
- blocks: [WO-nnn, ...]   (empty list = flags gate review only)
- ruling: PENDING
  <!-- becomes: <decision> — ruled_by <who>, <date>; propagated via spec-patch <commit> -->
```

PB proposals use the same shape: the executor believes an unsanctioned legacy behavior is wrong
→ it files the proposal here (kind: pb-proposal) and does NOT build the fix. A ruling either
adds a PB entry + divergence (sanctioning it) or declines (behavior stays FIXED).
