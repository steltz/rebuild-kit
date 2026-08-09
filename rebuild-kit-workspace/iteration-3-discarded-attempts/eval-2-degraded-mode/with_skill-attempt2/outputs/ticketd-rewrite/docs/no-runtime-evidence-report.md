# P2 — No Runtime Evidence Report

`rebuild.json.evidence.runtime_ingestion: "inactive"`. No access logs, APM export, analytics
events, or error-tracker dump were available at generation time (confirmed at intake — "no access
logs" was stated directly). Per `SKILL.md` Degraded Mode:

- `usage-weights.json` was generated as a **static proxy** (route presence, evenly weighted, with
  one down-weight based on an in-source comment, not traffic) — see that file's `note` field.
- `perf-envelopes.json` was **not produced**. No latency data exists to derive p50/p95/p99 from,
  and none was invented. There are therefore no NFR latency floors in this workspace; any
  performance targets in work orders are either absent or explicitly marked as a target
  the rewrite should meet on general principle (e.g. "don't block the request thread," PB-001)
  rather than a measured floor to preserve.
- The **zero-traffic report was not produced** — it requires an observation window, which does
  not exist. This means `docs/do-not-port.md` contains only entries backed by zero-*references*
  (static) evidence, never zero-*traffic* evidence. `app/legacy_import.py` is one such entry;
  it is NOT also claimed to be zero-traffic (it might still run out-of-band — see OQ-006).

## What changes when evidence lands

Tracked as OQ-007 in `docs/open-questions.md`. Once access logs or APM exports are available:

1. Run `python3 <skill>/scripts/evidence.py --root . --logs <files>`.
2. Replace `usage-weights.json` with the traffic-derived version; it will carry
   `"source": "observed"` instead of `"source": "static-proxy"`.
3. Generate `perf-envelopes.json` for the first time; treat its p95/p99 as new NFR floors.
4. Produce the zero-traffic report; re-evaluate `/internal/export/csv` and
   `app/legacy_import.py` against real traffic instead of source comments.
5. Re-score every WO's risk in `ledger.json` (inferred-claim ratio drops once traffic confirms
   or refutes the static proxy).
6. Set `rebuild.json.evidence.runtime_ingestion: "active"`.
