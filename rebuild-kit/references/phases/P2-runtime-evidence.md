# P2 — Runtime Evidence Ingestion

Outputs: `usage-weights.json`, `perf-envelopes.json`, scrubbed payload corpus
(`verification/replay/corpus/`), zero-traffic report (feeds `do-not-port.md`).

Runtime evidence is what separates "effort follows usage" from guessing. Access logs, APM
exports, analytics, and error-tracker dumps are ingested here; the payload corpus later seeds T2
replay inputs (P7).

## Procedure

1. **Collect** whatever the human granted in P0: access logs, APM/trace exports, analytics
   events, error-tracker issues. Confirm the PII-scrub approval covers each source.
2. **Ingest**:
   ```bash
   python3 <skill>/scripts/evidence.py --root <rewrite-root> --logs <files...> [--format auto]
   ```
   The script parses common formats (CLF/combined, JSON-lines), scrubs PII at intake
   (emails, tokens, bearer headers, obvious secrets — before anything is written into the
   workspace), joins against the P1 route map, and emits:
   - `usage-weights.json` — normalized request share per route (drives backlog order, P8)
   - `perf-envelopes.json` — p50/p95/p99 latency per route where the log format carries timing
     (these become NFR floors: the rewrite must not regress them)
   - zero-traffic report — routes present in code with no observed traffic over the window
3. **Judgment pass**: zero-traffic ≠ dead. Check the window (a year-end job looks dead in a
   March log), internal/admin paths, and webhook receivers. Promote to `do-not-port.md` only
   with corroborating static evidence; otherwise record as "low confidence, observed window: N
   days" in the report.
4. **Error-tracker issues** that reproduce a PB defect: attach the trace/issue link to the PB
   entry as additional evidence.

## Degraded mode

No runtime evidence at all: set `rebuild.json.evidence.runtime_ingestion: inactive`.
Usage weights fall back to a static proxy (route count × inbound-reference count) and every
artifact deriving from them says so (`"source": "static-proxy"`). Perf envelopes are simply
absent — never invented. The zero-traffic report is not produced (no observation window exists).
