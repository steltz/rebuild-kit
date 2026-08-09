# Fixtures

Every `*.json` file here (except this README) is a **bare payload**, not a wrapper object —
each one validates directly against a schema in `docs/contracts/openapi.yaml#/components/
schemas/` or against an inline response schema for a specific operation. Provenance for each
is recorded here, not embedded in the payload (embedding metadata fields would pollute what's
actually being schema-validated).

| File | Validates against | Provenance |
|---|---|---|
| `ticket.json` | `#/components/schemas/Ticket` | Real response body, verbatim, from `verification/replay/traces/legacy/tickets-get.jsonl#tickets-get-001-existing` — captured from a genuinely running legacy instance. |
| `ticket-not-found.json` | `GET /api/tickets/{id}` 200 response (empty-object variant) | Real response body from `tickets-get.jsonl#tickets-get-002-nonexistent`. |
| `create-ticket-request.json` | `#/components/schemas/CreateTicketRequest` | Real request body from `tickets-create.jsonl#tickets-create-001-happy`. |
| `create-ticket-response.json` | `#/components/schemas/CreateTicketResponse` | Real response body from the same trace. |
| `error-title-required.json` | `#/components/schemas/ErrorBody` | Real response body from `tickets-create.jsonl#tickets-create-002-missing-title`. |
| `error-invalid-token.json` | `#/components/schemas/ErrorBody` | Real response body from `auth-reset-confirm.jsonl#auth-reset-confirm-002-unknown-token`. |

## Validation

Run (stdlib + the vendored mini-YAML/JSON tooling, no extra deps beyond `pyyaml` for the
OpenAPI file itself):

```bash
python3 docs/contracts/validate_fixtures.py
```

This was run at generation time; see its own output for the pass/fail record. Every fixture
above validated successfully against its target schema before being committed.
