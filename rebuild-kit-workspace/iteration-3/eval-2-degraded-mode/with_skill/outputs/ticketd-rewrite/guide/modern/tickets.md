# Tickets (designed-not-built)

M0 (`WO-001`) ports list/create/get exactly, including the `200 {}`-not-404 quirk and the
unfixed slug-collision behavior — neither is a defect the problem brief asked to fix, so neither
gets "improved" along the way. M1 (`WO-002`) adds close, now dispatching its notification through
`WO-004`'s async boundary instead of blocking the request (see `guide/modern/notification.md`).

Two open questions block full parity: whether the out-of-domain-`priority` and non-string-`title`
crash paths get validated away or ported as-is (`OQ-005`, `OQ-006`) — WO-001 currently documents
carrying them forward exactly, pending a ruling.

No implementation exists yet. This chapter fills in with as-built detail (actual FastAPI routes,
Pydantic models, migration outcome) once M0 and M1 close.
