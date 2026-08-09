# **Tickets** (designed-not-built)

**Not yet built.** Designed in `docs/features/WO-000-bootstrap-walking-skeleton.md` (list, the
walking-skeleton slice) and `docs/features/WO-002-tickets-create-get-close.md` (create, get,
close). This chapter fills in as-built content once M0/M1 close — until then, everything below is
the design, not an observation.

The FastAPI/Postgres version of this subsystem is designed to be *behaviorally* nearly identical
to legacy — every FIXED behavior in the WOs above (no-pagination, `200 {}` on missing ticket,
int-or-string priority, collision-permitting slugs) is a hard requirement, not a starting point to
improve on, because PB-006 (no UI changes) means the client this API serves hasn't changed either.
The one real behavior change is *how* a ticket-close notification gets dispatched — see
`modern/notifications.md`; the close endpoint itself calls into that mechanism rather than sending
mail directly.

The P9 audit's four new coverage findings (empty-status-filter, non-object create body,
`priority: null`, non-numeric close-id) are folded into WO-002's scope and should be verified —
not assumed — when this chapter's as-built content gets written.
