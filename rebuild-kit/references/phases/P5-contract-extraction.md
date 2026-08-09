# P5 — Contract Extraction

Outputs: `docs/contracts/` — `openapi.yaml`, `schemas/` (JSON Schema for events/payloads),
`ddl.sql` (current schema, verbatim), `integration-notes.md`, `fixtures/` (golden payloads).

Freeze the boundaries in machine-checkable form. The executor validates against these rather
than interpreting prose — so precision here is worth more than anywhere else.

## Procedure

1. **HTTP surface → OpenAPI.** From the P1 route map + P4 specs: every route, params, request/
   response schemas including error shapes, auth requirements. Where the code accepts more than
   it documents (extra fields tolerated, string/number coercion), record the *observed* contract
   and flag the looseness in `integration-notes.md` — clients may depend on it (Hyrum's law).
2. **Events & async payloads → JSON Schema**, one file per message type, with the emitting and
   consuming sites cited in a header comment.
3. **DDL** — dump the current schema verbatim into `ddl.sql` (the migration target schema is
   P6's job, not here).
4. **Integration notes** — outbound dependencies: external APIs called, expected responses,
   timeout/retry behavior, sandbox availability. Webhooks received, their verification scheme.
5. **Golden fixtures** — real (scrubbed, from the P2 corpus) or realistic sample payloads per
   contract, stored under `fixtures/`; these seed characterization tests (P7) and are
   spot-checked in the audit (P9).

## Validation — contracts must be checkable, so check them

Lint the OpenAPI (any validator available — even `python3 -c "import yaml; yaml.safe_load(...)"`
beats nothing); validate each fixture against its schema. A fixture that fails its own schema is
a P5 bug: fix whichever is wrong, citing the code that settles it.

## Workflow shape

Fan out per boundary group (route prefix / message family), paired with a validator agent that
round-trips fixtures against schemas. Serial fallback is fine on small surfaces.
