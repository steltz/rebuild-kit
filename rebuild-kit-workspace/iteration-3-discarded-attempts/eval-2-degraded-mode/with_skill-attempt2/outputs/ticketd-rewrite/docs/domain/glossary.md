# Glossary

Terms as `legacy/` code uses them. Where a term's plain-English reading might diverge from what
the code actually does, that gap is called out — those gaps are ASK material if a future WO
relies on the distinction.

| Term | Code meaning | Notes |
|---|---|---|
| **ticket** | A row in `tickets`: title, slug, priority, status, timestamps. | No "type"/"category" field beyond priority; no description/body field exists at all — a ticket is title + metadata only. |
| **priority** | One of `low`/`med`/`high`, stored as text. Accepted on create as either the word or the string `"1"`/`"2"`/`"3"` (1=low, 2=med, 3=high). | Numeric strings outside 1-3 are NOT mapped and fall through to the raw INSERT — see `docs/domain/ticket.md` Invariants. Defaults to `"med"` if omitted (`server.py:47`). |
| **status** (ticket) | `open` or `closed` only. | No `in_progress`/`on_hold`/etc — the model is binary. |
| **close** | The one-way transition `open -> closed`, plus a notification email to a fixed address. | "Closing" is a verb tied 1:1 to the email side-effect (PB-1) — closing and notifying are not separable in the legacy code. |
| **slug** | A URL-safe derivation of `title`: lowercased, non-alphanumeric runs collapsed to `-`, trimmed, capped at 64 chars (`app/util.py`). | Not guaranteed unique. Not used as a lookup key anywhere (routes key by `id`, not `slug`) — its only consumer is the create-response body and the CSV export omits it entirely (exports id/title/status only, `server.py:114`). |
| **reset token** | An opaque string handed to a user to prove control of an email address, single-use, 30-minute lifetime. | Generated from MD5(email + timestamp) — see PB-002. Not tied to a `users` row; operates on free-text email. |
| **watchers** | The fixed recipient `watchers@example.internal` (`server.py:76`) that gets notified on every ticket close. | Not a table, not configurable in code — a hardcoded constant. Any "watchers" concept beyond this single hardcoded address does not exist in `legacy/`. |
| **assignee** | A `tickets.assignee_id` FK column pointing at `users.id`. | **Vestigial** — never set or read by any route. See `docs/domain/user.md`. Do not assume assignment is a working feature. |
| **internal bypass** | Request header `X-Internal-Bypass: 1` on `/api/auth/reset` that skips rate-limiting. | Undocumented outside the one code line that checks it (`server.py:84`). See OQ-004 — intent unconfirmed. |
