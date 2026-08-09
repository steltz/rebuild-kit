# ADR-003: Bug-for-bug wire compatibility by default, gated by flags

Status: accepted. Date: 2026-08-08.

## Context

We have zero evidence about clients (no logs, no UI source, no interviews yet). The
only safe default is: the rewrite's HTTP surface is indistinguishable from legacy,
including behaviors that look like bugs. Deviations are allowed only where an ADR
records them (currently: ADR-001 failure semantics, ADR-002 token format).

## Preserved quirks (numbers from `../inventory/behavior-inventory.md`)

| Q | Behavior | How preserved |
|---|----------|---------------|
| Q3 | Ad-hoc error bodies (`{"error": "title_required"}` etc.), never FastAPI's 422 shape | Handlers parse raw JSON themselves; no Pydantic validation on request bodies of compat routes |
| Q4 | No pagination on ticket list | No limit/offset params added |
| Q5 | Malformed/missing JSON body treated as `{}` | Explicit try/except around `request.json()` |
| Q6 | Priority accepted as int or string, `1/2/3` → low/med/high, default `med`; other values → 500 | Identical coercion code; CHECK constraint yields 500 |
| Q7 | Slug collisions allowed | No unique constraint on slug |
| Q8 | Missing ticket → `200 {}` | Explicit branch |
| Q9 | Close of missing/closed ticket → `200 {"closed": false}` | Conditional UPDATE, rowcount |
| Q12 | Expired == invalid token, same 403 body | Single error path |
| — | `assignee_id` present (null) in ticket JSON | Serializer includes all columns |
| — | CSV export byte-format incl. comma corruption | Same string join, no csv module |

## Compat flags (in `app/app/config.py`)

| Flag | Default | Meaning |
|------|---------|---------|
| `ENABLE_LEGACY_CSV_EXPORT` | `true` | Serve `/internal/export/csv` byte-compatibly. Flip off + remove after intake A1 proves no callers |
| `ALLOW_INTERNAL_BYPASS` | `false` | Honor `X-Internal-Bypass: 1` (ADR-002 — the one place we default to the safe side instead of the compatible side, because the compatible side is an unauthenticated rate-limit bypass) |
| `SMTP_LEGACY_HEADERLESS` | `true` | Send header-less email payloads exactly like legacy |

## Known divergences to watch in parity runs

- Timestamp serialization: legacy emits stored naive-local ISO strings; the rewrite
  stores timestamptz and serializes back to naive local in `LEGACY_TZ` (ADR-004).
  Sub-second precision may differ; parity tests compare to the minute.
- 404 body for non-integer ids (`/api/tickets/abc`): Flask HTML page vs FastAPI JSON
  `{"detail": "Not Found"}`. Assumed inconsequential `[A]`; parity asserts status only.
- Header casing/order, `Server` header, etc.: not preserved; assumed inconsequential `[A]`.

## Exit criterion

Compat flags and quirk-preserving branches are not forever. Each is removable once the
matching intake item (see `../evidence/intake-checklist.md`) proves no client depends
on it, or all clients are migrated. Track removals in the evidence log.
