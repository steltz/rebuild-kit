# **Tickets** (designed-not-built)

Not implemented yet — `modern/` is an empty tree until WO-001 (Milestone 0) lands. This
chapter fills in with as-built content as work orders close; until then it's the plan, not a
report.

**Designed to hold, unchanged**: list/create/get/close's response shapes, status codes, the
200-empty-object-on-missing-ticket quirk, and int-or-string `priority` coercion — all `FIXED`
per `docs/features/WO-001-walking-skeleton.md`, `WO-004-ticket-close.md`, and
`WO-006-ticket-get.md`.

**Designed to change**: ticket closing no longer sends its notification synchronously
(`WO-002`/`WO-004` — see `notifications.md`), and new tickets will eventually get a guaranteed-
unique slug (`WO-005`, currently blocked on a ruling — `docs/open-questions.md` OQ-001).

**Designed but flagged, not yet built**: the P9 adversarial audit found three uncovered edge
cases in the legacy behavior (`title: null`, an all-symbol title producing an empty slug, and
a non-dict JSON body) that WO-001/WO-005 need to add test coverage for before closing — see
`docs/features/draft/tickets-create.md`'s P9-audit-added statements.
