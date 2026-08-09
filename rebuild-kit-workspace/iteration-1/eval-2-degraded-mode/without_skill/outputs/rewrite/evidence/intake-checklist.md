# Evidence intake checklist

Work top to bottom the day each evidence source becomes available. Every item names
the decision it unblocks. Log findings in `evidence-log.md`.

## A. When access logs arrive

- [ ] **A1.** Hits on `GET /internal/export/csv` over the longest available window.
      Zero → flip `ENABLE_LEGACY_CSV_EXPORT` default to off, schedule removal.
      Nonzero → identify the caller. (Unblocks: ADR-003, dead-code table.)
- [ ] **A2.** Any requests carrying `X-Internal-Bypass: 1`, and their source IPs.
      None → delete the bypass path entirely. Some → find the caller, give it a real
      mechanism, then delete. (Unblocks: ADR-002, `ALLOW_INTERNAL_BYPASS`.)
- [ ] **A3.** Per-endpoint traffic volumes and p95 latency (if logged). Sizes the
      pagination question (Q4) and cutover risk.
- [ ] **A4.** User-Agent / client inventory: is "the UI" the only caller of
      `/api/tickets*`? Any scripts/cron callers? (Unblocks: how strictly Q5/Q6/Q8
      quirks must be preserved, and for how long.)
- [ ] **A5.** Frequency of `GET /api/tickets/{id}` for nonexistent ids — how hot is
      the 200-empty-object path (Q8) in practice.
- [ ] **A6.** 500-rate on `POST /api/tickets/{id}/close` and `/api/auth/reset`
      (SMTP-induced). Quantifies the Q10 partial-failure incident surface — useful for
      the "why outbox" writeup and for spotting clients with retry loops.

## B. When git history arrives

- [ ] **B1.** Commit that added `X-Internal-Bypass` — message/author/ticket reference
      usually names the intended caller. (ADR-002.)
- [ ] **B2.** Commit that added `/internal/export/csv` and any later touching commits.
      (ADR-003.)
- [ ] **B3.** History of `users` / `assignee_id`: was assignment functionality removed
      from the code at some point (then data may exist), or never built? (Q2.)
- [ ] **B4.** Any deleted endpoints/behaviors that production clients might still call
      (look for route deletions across history — a route removed from code may still
      be hit and 404 today; confirms tolerable-404 client behavior).
- [ ] **B5.** Churn hotspots — files edited most often are where the undocumented
      requirements live; re-read them with that lens.

## C. When production DB access arrives

- [ ] **C1.** Row counts: `tickets`, `users`, `reset_tokens`. (Q4 pagination; migration
      downtime; whether reset_tokens has years of never-purged rows.)
- [ ] **C2.** `SELECT DISTINCT priority FROM tickets` — any values outside
      low/med/high (possible if CHECKs were added after data existed, or if another
      writer bypasses them)? Same for `status`. (Migration: Postgres CHECKs will
      reject stragglers; decide map-or-carry per value.)
- [ ] **C3.** `SELECT COUNT(*) FROM users`; `SELECT COUNT(*) FROM tickets WHERE
      assignee_id IS NOT NULL`. Nonzero → find the external writer before cutover
      (dead-code table item 3). (Q2.)
- [ ] **C4.** Sample `created_at`/`closed_at` values: confirm they are all ISO-format
      naive local strings; look for format drift across years (2019-era rows may
      differ). Determine server timezone from ops. (Migration plan, ADR-004.)
- [ ] **C5.** Slug duplicates: `SELECT slug, COUNT(*) FROM tickets GROUP BY slug
      HAVING COUNT(*) > 1`. Confirms Q7 collisions exist in the wild → slugs must stay
      non-unique in Postgres too.
- [ ] **C6.** Any `closed_at IS NOT NULL AND status = 'open'` or other invariant
      violations the migration script must tolerate.
- [ ] **C7.** Titles containing commas/newlines/control chars — quantifies the CSV
      corruption (ADR-003) and tests the migration's string handling.

## D. People to find (no system access needed — start now if anyone is reachable)

- [ ] **D1.** Whoever operates "the UI": confirm Q4 (no pagination) and Q8
      (200-empty-object) dependencies, and get the UI source.
- [ ] **D2.** Whoever consumes `reset/confirm`'s `{"ok", "email"}` response — the
      actual password-changing system. Frozen contract until found.
- [ ] **D3.** Ops: server timezone (C4), SMTP relay details, network controls that
      justify the no-auth posture (Q1), and how legacy is actually deployed.
- [ ] **D4.** Whether `watchers@example.internal` is read by anyone.
