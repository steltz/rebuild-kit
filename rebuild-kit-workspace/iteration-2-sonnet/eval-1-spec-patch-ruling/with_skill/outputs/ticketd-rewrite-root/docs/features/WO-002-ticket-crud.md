# WO-002 — ticket CRUD
id: WO-002    depends_on: []    milestone: M1    gate: false    context_budget: ~250 lines
behaviors:
  - statement: GET /api/tickets/<id> returns 200 with {} for missing tickets, never 404 (legacy UI depends on it).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:58-64]
  - statement: Slug generation lowercases the title, collapses non-alphanumeric runs to a
      single hyphen, strips leading/trailing hyphens, and truncates the result to 64 chars.
    fidelity: FIXED
    evidence: [ticketd/app/util.py:4-6]
  - statement: Generated slugs must be unique among stored tickets. On collision with an
      existing stored slug, append a numeric suffix to the generated base slug — `-2` for the
      first collision, `-3` for the next, and so on — and use the first suffixed candidate that
      is not already taken. Existing stored slugs are not migrated or regenerated; only newly
      generated slugs are subject to this check.
    fidelity: REPAIR — target: unique slugs via numeric-suffix disambiguation (ruled OQ-002,
      Dana Ruiz, 2026-08-08)
    evidence: [ticketd/app/util.py:4-6, PB-003]   divergence: ED-002
  - statement: The slug written to the ticket row and the slug returned in the POST /api/tickets
      response body must be the same value, computed once. Legacy calls `slugify(title)`
      independently for the INSERT and for the response (server.py:51,55); this was harmless
      there because slugify is a pure function, but under the new uniqueness rule slug
      generation becomes stateful (it depends on what's already stored) — a second independent
      call after the INSERT would see the just-inserted row and could append an extra,
      spurious suffix, making the stored and returned slugs disagree.
    fidelity: REPAIR — target: compute the (possibly-suffixed) slug once and reuse it for both
      the stored row and the response body (corollary of OQ-002, Dana Ruiz, 2026-08-08 — no
      independent ruling text, but required to satisfy "slugs must be unique" without
      introducing a new discrepancy class)
    evidence: [ticketd/app/server.py:51,55]   divergence: ED-002
  - statement: Whether the numeric suffix counts against the 64-char cap (i.e. whether the base
      slug is truncated further to make room for `-2`, `-3`, ...) is not specified by the ruling.
      Note also that if a truncated base slug ends in a hyphen, naive suffixing could produce a
      double hyphen (e.g. `foo--2`); collapsing that is likewise unspecified.
    fidelity: FREE — outcome required is a unique slug of at most 64 chars with no double
      hyphens; how truncation and suffixing interact is an implementation choice.
acceptance:
  replay_set: tickets-*.jsonl
