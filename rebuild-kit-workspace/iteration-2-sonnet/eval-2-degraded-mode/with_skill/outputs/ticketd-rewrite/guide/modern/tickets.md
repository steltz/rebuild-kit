# Tickets (designed-not-built)

**Designed, not built** — no code exists in `modern/` yet (`WO-001` and `WO-002` implement this).

As designed: same four routes on FastAPI + PostgreSQL. Every FIXED behavior in
`guide/legacy/tickets.md` carries forward unchanged, INCLUDING the `200 {}` not-found quirk and
the unenforced slug uniqueness — this is a faithful port for anything not explicitly named in
`docs/problem-brief.md`. Two open items from the P9 audit (`docs/open-questions.md#OQ-008`,
`#OQ-009`) may force a real design decision here: FastAPI's Pydantic-based request validation
might reject a non-string `title` or a null `priority` automatically, before application code
ever runs — which would mean "porting today's unhandled-500 behavior" isn't achievable without
deliberately working against the framework. That's a human call, not a mechanical one; see the
OQ entries.

This chapter will fill in with as-built detail (actual module layout, the FREE choice made for
the DB access layer, etc.) as WO-001/WO-002 close — per the guide's regeneration lifecycle,
never hand-edited here.
