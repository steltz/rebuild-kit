# Adversarial Audit Report — ticketd

<!-- Generated P9, 2026-08-08. SERIAL MODE (single-session generation, no subagents
     available): independence approximated per the playbook — every claim re-derived from
     the pinned source and the captured traces alone, in a separate pass from extraction,
     reading only the citations, never the extraction notes. This is weaker than
     fresh-context adversaries; treat "confirmed" here as "confirmed under serial
     approximation" and re-attack opportunistically during execution. -->

## Scorecard

| Metric | Value |
|---|---|
| Claims audited / confirmed / contradicted / unverifiable | 43 / 41 / 1 / 1 |
| Claims confirmed | 95.3% |
| Spec branch coverage (branches in live source represented in specs) | 100% (21/21 — small app; enumeration in per-module table) |
| Problem coverage (PB entries dispositioned) | 100% (5/5) |
| Demotion rate (claims → ASK) | 0% (2 pre-existing ASKs from P4 stand; audit added coverage items, no new demotions) |
| Fixture spot-check | 7/7 validate (see below) |

## Per-module results

| Module | Claims | Confirmed | Contradicted | Unverifiable | New coverage items |
|---|---|---|---|---|---|
| tickets/list (TL) | 6 | 5 | 1 (TL-5) | 0 | 0 |
| tickets/create (TC) | 10 | 10 | 0 | 0 | 2 (TC-11, TC-12) |
| tickets/get (TG) | 3 | 3 | 0 | 0 | 1 (TG-4) |
| tickets/close (CL) | 6 | 6 | 0 | 0 | 0 |
| auth-reset/request (RR) | 8 | 7 | 0 | 1 (RR-1 leg) | 0 |
| auth-reset/confirm (RC) | 7 | 7 | 0 | 0 | 1 (dup-token note, below) |
| notification (NT) | 3 | 3 | 0 | 0 | 0 |

## Discrepancies (each already applied to the specs — this is the record)

### AD-001 — TL-5 claimed "L3 normalizes tie order via sort_by:id" (tickets-list.md)
- verdict: contradicted — `verification/replay/diff-rules.yaml` contains no sort rule;
  the original claim described tooling that does not exist.
- action taken: spec edited — tie order is explicitly unspecified on both sides; replay
  inputs avoid ties (microsecond timestamps). No behavior claim changed.

### AD-005 — RR-1's "empty email → 200" is sink-conditional
- verdict: unverifiable (in prod) — under the harness sink the trace shows 200; a real
  SMTP server may refuse recipient `""` → unhandled exception → 500 after the insert.
  The 30-day log shows no 5xx on POST /api/auth/reset, consistent with the input simply
  not occurring.
- action taken: spec annotated; moot post-repair (ED-003 decouples dispatch, modern
  legitimately returns 200). Not demoted: the modern-facing statement is well-defined.

## Coverage-hunt findings (branches/edges in source with no spec item — all routed)

- **AD-002** `slugify` operation order: `strip("-")` before `[:64]` → truncated slugs can
  end in `-`; all-symbol/non-ASCII titles slug to `""`. → new spec item TC-11 (FIXED as-is;
  folded into OQ-001's ruling scope). `ticketd/app/util.py:6`.
- **AD-003** priority coercion boundary: floats (`2.0`) and `null` are NOT coerced and hit
  the 500 path. → new spec item TC-12 under OQ-007. `ticketd/app/server.py:47-49`.
- **AD-004** negative IDs never match `<int:tid>` (unsigned converter) → framework 404. →
  new spec item TG-4. `ticketd/app/server.py:58`.
- Duplicate token values in the bare `reset_tokens` table are theoretically possible
  (no constraint); `fetchone()` picks arbitrarily and `DELETE ... WHERE token=?` removes
  all duplicates. Practically unreachable (md5 over email+float time); noted in
  `docs/domain/reset-token.md`'s invariants, no spec item warranted. Modern's UNIQUE
  token_hash forecloses it.
- Evidence conflicts already registered from P2: OQ-008 (unexplained prod 5xx),
  OQ-009 (log 200 vs code 201 on create). `ticketd/app/notify.py:1` docstring's "~2s
  typical" also conflicts with the observed close p50 of 110ms — the docstring overstates;
  envelopes are authoritative for NFR-2.

## Fixture spot-check

7/7 pass: ticket-open/ticket-closed vs the OpenAPI Ticket schema; mail-close/mail-reset vs
mail-message.schema.json; all 3 error fixtures vs the Error schema (validated with
jsonschema; runner output in generation log). OpenAPI parses clean.

## Problem coverage

PB-001 REPAIR in WO-004/WO-005 (ED-001/ED-003) · PB-002 REPAIR in WO-005/WO-006 (ED-002) ·
PB-003 REPAIR in WO-002, target pending OQ-001 · PB-004 recorded (rebuild.json,
modern/CLAUDE.md) · PB-005 out-of-scope ruling enforced as FIXED tags + L3. No
UNDISPOSITIONED entries; assembly unblocked.

## Standing caveats for gate-signers

1. Serial-mode audit (header note) — independence is approximated, not structural.
2. Harness runs legacy on Flask 3.1 vs prod's "Flask 1.x era" (requirements-legacy.txt
   note); app-level behaviors are version-stable, framework error *pages* are compared at
   status+media-type only.
3. Expiry (RC-3) is verified by characterization with a DB aging hook, not by replay
   traces (clock control); the hook runs against both trees.
