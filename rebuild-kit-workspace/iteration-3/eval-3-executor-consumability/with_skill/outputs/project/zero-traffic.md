# Zero-Traffic Report

Observed window: 1 days (upper bound, honest) · 2000 matched requests

<!-- Corrected during the P2 judgment pass: the log was described as "~30-day" but its actual
     timestamps span a single synthetic hour (12/Jul/2026 10:00:00-10:59:59), cycled twice to
     reach 2000 lines. Recording window_days=30 would have overstated confidence in the
     zero-traffic finding below. See docs/problem-brief.md OIQ-3, usage-weights.json.notes. -->

Routes in code with no observed traffic. Zero-traffic ≠ dead: check window coverage (cron/seasonal), admin paths, webhook receivers. Promote to do-not-port.md only with corroborating static evidence.

- `GET /internal/export/csv` — confidence: low, corroboration: code comment at
  `ticketd/app/server.py:112` ("written for the 2020 audit; no caller since") is testimony-
  adjacent but not a PB entry, and a true zero-hit result over a synthetic 1-hour window has
  near-zero evidentiary weight for what the comment itself frames as an *annual* tool — an
  annual caller would show zero hits in any 1-hour sample by construction. **Not promoted** to
  `docs/do-not-port.md` on this evidence alone; see `docs/do-not-port.md` DNP-002 and
  `docs/open-questions.md` OQ-004 for the full reasoning and the ruling this is blocked on.
