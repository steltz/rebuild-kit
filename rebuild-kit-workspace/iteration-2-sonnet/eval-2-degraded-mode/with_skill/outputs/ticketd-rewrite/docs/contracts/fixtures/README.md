# Fixtures

<!-- P5. No P2 scrubbed corpus exists this run (no runtime evidence granted) — these are
     REALISTIC SAMPLE payloads (input tier T3, provisional), not real captured traffic (T1).
     Each is validated against docs/contracts/openapi.yaml's component schemas below. When real
     traffic becomes available, replace/augment with actual (scrubbed) examples via spec-patch
     and reclassify as T1/T2. -->

| Fixture | Endpoint | Tier |
|---|---|---|
| `ticket-create-request.json` / `ticket-create-response.json` | `POST /api/tickets` | T3 |
| `ticket-get-found.json` | `GET /api/tickets/{tid}` (found) | T3 |
| `ticket-get-not-found.json` | `GET /api/tickets/{tid}` (missing — the `{}` quirk) | T3 |
| `ticket-list-response.json` | `GET /api/tickets` | T3 |
| `ticket-close-response.json` | `POST /api/tickets/{tid}/close` | T3 |
| `reset-request-response.json` | `POST /api/auth/reset` (200) | T3 |
| `reset-rate-limited-response.json` | `POST /api/auth/reset` (429) | T3 |
| `reset-confirm-response.json` | `POST /api/auth/reset/confirm` (200) | T3 |
| `reset-invalid-token-response.json` | `POST /api/auth/reset/confirm` (403, either cause) | T3 |
| `export-csv-response.csv` | `GET /internal/export/csv` | T3 |

Validated by `scripts/validate_fixtures.py` (ad hoc, run once during P5; see its output recorded
in `docs/contracts/fixtures/validation-log.txt`).
