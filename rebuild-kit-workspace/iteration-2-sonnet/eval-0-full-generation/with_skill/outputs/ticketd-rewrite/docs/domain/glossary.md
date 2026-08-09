# Glossary

Domain terms as the code uses them. Where a term is ambiguous or code vocabulary might not
match how support/leadership talk about it, that gap is called out explicitly — it's ASK
material, not something to silently resolve.

| Term | Meaning as coded | Source | Notes |
|---|---|---|---|
| **ticket** | A row in `tickets`: title, slug, priority, status, optional assignee, timestamps | `db/schema.sql:1-10` | |
| **slug** | Lowercased, non-alphanumeric-collapsed-to-hyphen, 64-char-truncated derivation of `title`, computed once at create | `app/util.py:4-6` | Collision-prone by construction (PB-003); "slug" here has no relation to any concept of a stable/external ticket identifier beyond this string — unclear if any external system (URLs? integrations?) actually depends on slug *values* being stable, vs. just being present. Not asked, not assumed — see OQ-001. |
| **priority** | One of `low`/`med`/`high`, stored as TEXT; API also accepts `"1"/"2"/"3"` as synonyms for the same three values, defaulting to `"med"` | `app/server.py:47-49`, `db/schema.sql:5` | The int-string convention (`"1"→low, "2"→med, "3"→high`) has no explanation in code or comments — plausibly a legacy client sent numeric IDs before a `svc-ui` update switched to words, and both are kept for compatibility. Inferred, not confirmed — flagged low-confidence in the P4 spec, not asserted as fact. |
| **status** | One of `open`/`closed`; ticket lifecycle has exactly these two states, no "in progress" or similar | `db/schema.sql:6` | |
| **close** (verb) | Sets `status='closed'`, stamps `closed_at`, fires a notification email — all three happen only if the ticket wasn't already closed (checked via `status != 'closed'` in the UPDATE's WHERE clause) | `app/server.py:67-77` | |
| **reset token** | A single-use, time-limited credential proving control of an email address, used to authorize a password change (though no password-change route exists in this codebase — see below) | `app/server.py:80-108`, `db/schema.sql:18-22` | |
| **watchers** | The fixed recipient `watchers@example.internal` that every ticket-close notification is sent to | `app/server.py:76` | Hardcoded literal, not a table or list — "watchers" is not a modeled entity anywhere, just an address baked into the close handler. Every ticket close notifies the same single mailbox regardless of ticket content, assignee, or reporter. |
| **rate limit bypass** | `X-Internal-Bypass: 1` header that skips the 3/hour reset rate limit entirely | `app/server.py:84` | Undocumented. See `docs/open-questions.md` OQ-006. |

## A term that's conspicuously absent: "password"

The reset flow issues and confirms tokens, but **no route in this codebase ever changes a
password** — there's no `users.password` column, no `PATCH`/`PUT` route, nothing. The
confirm-reset response returns `{"ok": true, "email": row["email"]}` and stops. Either: (a)
password storage/verification lives entirely outside this legacy tree (another service this
one hands the confirmed email off to, out of band), or (b) this flow is dead/partial
functionality. Not resolved by any evidence in this tree — carried to `docs/open-questions.md`
as OQ-008 rather than assumed either way. This has real weight for the rewrite: PB-002's REPAIR
target ("secure token generation/storage") should not accidentally imply "and also implement
password changing," which nobody asked for (PB-005 non-goals lean toward no new features).
