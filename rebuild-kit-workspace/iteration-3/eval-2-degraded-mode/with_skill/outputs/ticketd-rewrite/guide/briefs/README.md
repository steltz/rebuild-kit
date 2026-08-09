# Briefs

- **Ruling briefs** (`OQ-*-ruling-brief.md`) — one per open question filed during generation
  (OQ-001 through OQ-006). All six exist here now, generated at P10, since every OQ that could
  block a WO or flag a gate was already known at generation time.
- **Gate packets** (`WO-*-gate-packet.md`) — intentionally NOT generated yet. The template
  (`templates/gate-packet.md`) asks for "what was built" and verification results, and nothing
  has been built — `modern/` is empty by design at this point in the pipeline (see root
  `CLAUDE.md`'s scope boundary). The root `CLAUDE.md` executor loop (step 7) generates these
  automatically when a gate WO actually halts during execution. Fabricating one now would mean
  describing an implementation that doesn't exist — exactly what the honesty rules in
  `phases/P10-field-guide.md` forbid.
