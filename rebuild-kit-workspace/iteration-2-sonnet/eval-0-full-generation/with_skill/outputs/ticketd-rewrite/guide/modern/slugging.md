# **Slugging** (designed-not-built)

Not implemented yet, and cannot be until a human rules on `docs/open-questions.md` OQ-001 —
see `docs/features/WO-005-slug-uniqueness.md`. One thing is already settled: `tickets.slug`
will be `UNIQUE` at the database level, which it isn't today. What's not settled: what happens
when a new ticket's slug would collide (reject the request? auto-suffix? include the ticket id
in every slug, not just colliding ones?), and what to do about any pre-existing collisions in
production data once the census (`docs/migration/census.md` probe #26) comes back with real
numbers. The executor is instructed to skip this work order, not guess, until it's ruled.
