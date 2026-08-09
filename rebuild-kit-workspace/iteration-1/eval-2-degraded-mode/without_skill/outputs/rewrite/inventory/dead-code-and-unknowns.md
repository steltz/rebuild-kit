# Dead-code candidates and load-bearing unknowns

Nothing here may be deleted or "fixed" until the matching item in
`../evidence/intake-checklist.md` is answered. Tags per `../README.md`.

## Dead-code candidates (do NOT assume dead)

| Item | Why it looks dead | What would prove it | Scaffold stance |
|------|-------------------|---------------------|-----------------|
| `GET /internal/export/csv` | `[S]` comment "no caller since 2020 audit" | Access logs: zero hits over a representative window; git history: who added it, any later references | Ported, behind `ENABLE_LEGACY_CSV_EXPORT` (default on), byte-compatible |
| `app/legacy_import.py` | `[S]` "nothing imports this module" — confirmed by grep of the codebase | Nothing external can import a module from a service process; safe to call dead from source alone | Not ported |
| `users` table + `tickets.assignee_id` | `[S]` no code path reads/writes users or sets assignee_id | Prod DB: are there rows in `users`? non-null `assignee_id`? If yes, **something outside this codebase writes the SQLite file directly** — that writer must be found before cutover | Schema ported as-is; columns kept in API output |
| `X-Internal-Bypass: 1` header | Undocumented; unknown callers | Access logs: any requests carrying the header; git history: commit message that introduced it | Ported behind `ALLOW_INTERNAL_BYPASS` (default OFF — it is also a security hole) |

## Load-bearing unknowns `[U]`

1. **Who consumes `POST /api/auth/reset/confirm`'s `{"ok", "email"}` response?**
   This codebase stores no passwords. Some other system completes the reset. Until it
   is identified, the response shape (including the `email` field) is frozen.
2. **What writes `users` / `assignee_id`?** See table above. If a direct-to-SQLite
   writer exists, the Postgres cutover breaks it silently.
3. **Server timezone** for interpreting naive `created_at`/`closed_at` strings during
   migration. See `../migration/data-migration-plan.md`.
4. **Actual clients of the API.** "The UI" is referenced by comments (no-pagination
   comment server.py:35, empty-object-404 comment server.py:62) but was not part of the
   handover. We don't know if it's the only client.
5. **Traffic volume and table sizes.** Affects: pagination decision (Q4), whether the
   unbounded `reset_tokens` table is already huge, migration downtime budget.
6. **Is `watchers@example.internal` an alias/list, and does anyone still read it?**
7. **Delivered email format** — legacy sends header-less SMTP payloads; how do these
   actually render for recipients, and does any automation parse them?
8. **Deployment reality**: how legacy is run (bare `app.run` dev server? behind what
   proxy? what network controls make the total absence of auth acceptable?). The
   rewrite scaffold also ships without auth to stay wire-compatible — that is only
   safe if the same network controls exist `[A]`.
