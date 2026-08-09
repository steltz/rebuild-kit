# tickets (designed-not-built)

<!-- Status: designed-not-built. Fills in as-built as M0/M1 close. -->

As designed (WO-001..WO-004): FastAPI routers over Postgres
(`docs/migration/target-schema.sql`), reproducing the observed contract exactly —
including the parts FastAPI will fight you on (`modern/CLAUDE.md`): the 200-`{}`
missing-ticket response, tolerated non-JSON bodies, int-or-string priority coercion, the
`med` spelling, no pagination. Framework validation defaults must be suppressed wherever
`docs/contracts/openapi.yaml` says the legacy contract is looser (or stricter) than
FastAPI's reflexes.

What changes, visibly: closing a ticket no longer waits on SMTP — the watcher mail goes
through the transactional outbox (ED-001). Slug behavior is *unchanged for now*: it stays
collision-prone until OQ-001 is ruled, then WO-002 patches to the ruled target.

As-built notes land here per milestone close (executor loop step 8).
