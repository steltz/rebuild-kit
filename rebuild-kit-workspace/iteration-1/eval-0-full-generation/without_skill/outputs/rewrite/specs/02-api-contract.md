# 02 — Target API contract

The new FastAPI service exposes exactly this surface. Anything not listed here is not part
of the product. Wire compatibility with `svc-ui/2.1` is the binding constraint; numbered
references (e.g. 3.2) point at `01-legacy-inventory.md`.

Conventions:
- All request/response bodies are JSON (`application/json`) unless stated.
- `Ticket` object (exact keys, no extras, no omissions):

```json
{
  "id": 42,
  "title": "Fix DB",
  "slug": "fix-db",
  "priority": "med",          // "low" | "med" | "high"
  "status": "open",           // "open" | "closed"
  "assignee_id": null,        // int | null
  "created_at": "2026-08-08T14:03:11.123456",  // see Timestamps note
  "closed_at": null           // string | null
}
```

**Timestamps** (Q5): stored as UTC `timestamptz`; serialized as ISO-8601. Legacy emitted
naive local time with no offset. Default decision: serialize as **naive UTC** (no `+00:00`
suffix) to keep the string shape identical (`YYYY-MM-DDTHH:MM:SS.ffffff`); absolute values
shift from local to UTC — verify svc-ui tolerance before cutover (verification checklist
item V-9).

---

## GET /api/tickets

- Query: `status` (optional, string, no validation — unknown values simply match nothing).
- 200: JSON array of `Ticket`, ordered `created_at DESC` (tie-break `id DESC` — pick a
  deterministic order; legacy was unspecified on ties).
- No pagination. Do not add `limit`/`offset` (out of scope).

## POST /api/tickets

- Body: `{"title": str, "priority"?: str|int}` — extra keys ignored (2.8).
- Validation (all failures must not be FastAPI's default 422 envelope — match legacy bodies):
  - Missing body / non-JSON body → treat as `{}` (2.2).
  - `title` absent or whitespace-only → **422** `{"error": "title_required"}` (2.1).
  - `priority` normalization: `str(value)`; `"1"→"low"`, `"2"→"med"`, `"3"→"high"`;
    `"low"/"med"/"high"` pass through; absent → `"med"`; anything else → **422**
    `{"error": "invalid_priority"}` (2.4 — deliberate improvement over legacy 500).
- Effect: insert ticket, `status='open'`, `created_at=now(UTC)`, slug per slug policy (Q1).
- 201: `{"id": <int>, "slug": "<slug>"}` (2.6).

## GET /api/tickets/{id}

- `id` must be an integer path segment; non-integer → **404** plain (3.3).
- Found → 200 `Ticket`.
- Not found → **200 `{}`** (3.2 — legacy UI depends on this; never 404).

## POST /api/tickets/{id}/close

- No body required; any body ignored.
- Effect (single DB transaction):
  1. `UPDATE ... SET status='closed', closed_at=now() WHERE id=:id AND status != 'closed'`.
  2. If a row changed: insert outbox row `{to: "watchers@example.internal", body:
     "closed: <title>"}` (4.3, `04-notifications.md`).
- 200 `{"closed": true|false}` — false for already-closed AND for nonexistent ids (4.2).
- Never blocks on or fails due to SMTP (4.5).

## POST /api/auth/reset

- Body: `{"email": str}` — absent → `""` (5.1).
- Rate limit: 3 per rolling hour per email → **429** `{"error": "rate_limited"}` (5.2).
  Bypass header per Q2 decision (default: keep `X-Internal-Bypass: 1`, gated behind config
  flag `RESET_RATE_BYPASS_ENABLED`, default **off** in prod until an owner is found).
- Effect: create token per `05-security-reset.md`; enqueue email to the given address, body
  `reset token: <token>` (5.4).
- 200 `{"ok": true}` — always, including unknown emails (5.1, non-disclosure).

## POST /api/auth/reset/confirm

- Body: `{"token": str}` — absent → `""`.
- Invalid, expired, or already-used → **403** `{"error": "invalid_token"}` — identical body
  for every failure mode (6.1).
- Success: atomically consume token (6.3) → 200 `{"ok": true, "email": "<email>"}` (6.4).

---

## Error envelope summary

| Case | Status | Body |
|---|---|---|
| Missing title | 422 | `{"error": "title_required"}` |
| Bad priority (new) | 422 | `{"error": "invalid_priority"}` |
| Reset rate limited | 429 | `{"error": "rate_limited"}` |
| Bad/expired/used token | 403 | `{"error": "invalid_token"}` |
| Unhandled server error | 500 | `{"error": "internal"}` (new; legacy emitted HTML — not contractual) |

FastAPI's default validation error shape (`{"detail": [...]}`) must never leak on these
endpoints — install custom handlers and parse bodies manually where the contract demands
legacy shapes.

## Removed endpoints

- `GET /internal/export/csv` — not implemented (Q3). If Q3 resolves to "keep", implement
  with proper CSV quoting and the same 3 columns.

## Health (new, additive)

- `GET /healthz` → 200 `{"status": "ok"}` (liveness; DB ping in readiness variant if the
  deploy platform wants it). Additive endpoints are allowed; changed/removed ones are not.
