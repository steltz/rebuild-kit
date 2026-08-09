# Open Questions and Risk Register

Every row is something the rewrite preserved or guessed at because no
evidence was available to decide it properly. "Evidence needed" says what
would resolve it. Ordered roughly by priority.

| # | Item | Source | Current handling in rewrite | Risk if wrong | Evidence needed |
|---|---|---|---|---|---|
| 1 | `X-Internal-Bypass: 1` skips the reset rate limit entirely, with no auth on the header itself | `server.py:84` | Preserved verbatim (comparison made constant-time, behavior unchanged) | If nothing legitimate uses it, it's a standing way to brute-force reset-request spam past the rate limit; if something *does* use it, removing it would break that caller | Access logs: does any request ever carry this header? From what source IP/service? |
| 2 | `GET /api/tickets/{id}` returns `200 {}` for a missing ticket instead of `404` | `server.py:62-63`, comment claims legacy UI depends on it | Preserved verbatim | If the comment is stale, we're perpetuating a genuine API smell into a "clean" rewrite for no reason | Frontend source, or logs showing how callers handle a `{}` body vs an absent one |
| 3 | `GET /api/tickets` has no pagination; comment says the UI fetches everything and filters client-side | `server.py:35` | Preserved verbatim | Unknown current ticket volume — could be fine forever, or could already be a slow endpoint | Row count from prod DB (Phase 2) + whether frontend can consume a paginated response (needs frontend source) |
| 4 | `/internal/export/csv` is unauthenticated; comment says "no caller since [2020 audit]" | `server.py:111-115` | Ported as-is, unauthenticated | Could be dead code carrying real risk (unauthenticated data dump) for zero benefit, or could still be polled by something we don't know about | Access logs for this specific path |
| 5 | `slugify()` allows collisions; schema has no uniqueness constraint on `slug` | `util.py:5`, `db/schema.sql` | Preserved; Postgres schema also has no unique constraint on `slug` | Unknown whether anything (routing, dedup, external links) assumes slug uniqueness | Duplicate-slug count from a real DB read (Phase 2) |
| 6 | Trailing `# tweak 1` / `# tweak 2` / `# tweak 3` comments with no code | `server.py:120-122` | N/A — nothing to port | Might reference removed functionality we're unknowingly not replicating | Git history |
| 7 | `reset_tokens` (legacy) / would-be equivalent are never pruned once expired-but-unused | `server.py` (no cleanup path found) | New schema keeps rows (with `used_at`) rather than deleting; no pruning job added | Unbounded table growth over years, though at low severity for an internal tool | Traffic volume to judge whether a cleanup job is worth building now vs. later |
| 8 | Server timezone at write time for legacy `created_at`/`closed_at` (`datetime.now()`, naive) | `server.py:52,71` | Rewrite defaults new writes to `TIMESTAMPTZ`/UTC; migrated historical rows (Phase 2) must NOT be assumed UTC without checking | Wrong timestamps on migrated historical tickets if the server wasn't actually running in UTC | Confirm legacy server's OS timezone before writing the Phase 2 migration script |
| 9 | Deployment/runtime environment for the new stack (container orchestrator, secrets manager, managed Postgres vs. self-hosted, whether an external queue like SQS/Redis is already available) | Not in handover | `docker-compose.yml` covers local dev only; outbox pattern chosen specifically to avoid assuming any external queue exists | Local-dev setup may not match what production actually needs (connection pooling limits, worker replica count, secrets injection) | Whatever infra documentation or platform-team input becomes available |
| 10 | Actual request volume / concurrency (informs Postgres pool size, worker poll interval/batch size in `rewrite/app/config.py`) | Not in handover | Conservative defaults, explicitly marked `EVIDENCE-NEEDED` in `rewrite/app/config.py` | Under- or over-provisioned once real load hits | Access logs / load test once environment exists |

## Explicitly out of scope for this pass

- Any authentication/authorization redesign beyond the two named fixes —
  the legacy app appears to have none on most routes; adding auth broadly
  would be a scope decision, not a bug fix, and wasn't asked for.
- Frontend/UI work — no frontend source was provided.
- Performance tuning — no traffic data exists to tune against.
