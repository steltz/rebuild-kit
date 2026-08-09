# **Notifications** (how it works today)

This is PB-001, the reason leadership approved the whole rewrite. `app/notify.py` is seven
lines: open an SMTP connection to `smtp.internal:25` with a 30-second timeout, send, done. Its
own docstring is candid about the cost: "Blocks the request thread; ~2s typical, 30s on
provider trouble." It's called from exactly two places, both **synchronously, inside the
request that triggers it**:

- `close_ticket` (`server.py:76`) — email `watchers@example.internal` when a ticket closes.
- `request_reset` (`server.py:94`) — email the reset token to whoever asked for it.

The mechanism itself was never touched again after the initial 2019 import — every later fix
attempt (three separate "hotfix: reset flow" commits) touched the *caller* in `server.py`, not
`notify.py`. Worth knowing: in `close_ticket`, the database UPDATE that actually closes the
ticket **commits before** the email is attempted (`server.py:69-72` vs. `:76`). So a slow or
down SMTP server today doesn't just make the request slow — it can make a ticket that
successfully closed report back as a 500, because the uncaught exception happens after the
state change already landed. That mismatch between "what actually happened" and "what the
client was told" is the real shape of the June incident, not just raw latency.

Full detail: `docs/features/draft/tickets-close.md` and `auth-reset-request.md`; the mechanism
fix itself is `docs/features/WO-002-async-notification-dispatch.md`.
