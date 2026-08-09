# guide/briefs/

Two ruling briefs pre-generated at workspace-generation time (`OQ-004`, `OQ-007`) — the two open
questions judged most likely to need a human's attention before or during M1 (OQ-004 because it
touches every route; OQ-007 because it gates WO-003's sign-off directly). The other seven open
questions (`OQ-001`, `OQ-003`, `OQ-005`, `OQ-006`, `OQ-008`, `OQ-009`) don't yet have a brief —
generate one identically from `docs/open-questions.md` + `references/templates/ruling-brief.md`
when they're closer to actually blocking work (OQ-001/003/005 before WO-006 starts, in
particular). Gate packets (`WO-*-gate-packet.md`) don't exist yet because no WO has closed —
per root `CLAUDE.md`'s executor loop, those get emitted when a gated WO actually halts for
sign-off, not at generation time.
