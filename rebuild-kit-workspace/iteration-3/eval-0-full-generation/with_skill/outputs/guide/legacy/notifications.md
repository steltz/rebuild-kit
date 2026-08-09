# **Notifications** (how it works today)

Seven lines of code (`ticketd/app/notify.py`), and it's the reason this whole rewrite exists.
`send_mail(to, body)` opens a plain SMTP connection to `smtp.internal:25` with a 30-second
timeout, sends, closes. No retry, no queue, no async — just a blocking call, invoked directly
inside two request handlers (ticket-close, reset-request). The module's own docstring is honest
about it: "~2s typical, 30s on provider trouble." In June 2026, provider trouble happened, and
because closing a ticket waits on this exact call, ticket-closing was unavailable for about 40
minutes org-wide (PB-001) — that's the incident that got this rewrite approved.

One thing worth noting for whoever builds the replacement: the database write always commits
*before* the send is attempted, both places this is called. That's good — a slow or failed email
never rolls back a ticket close or a token being issued. But it also means a process crash between
that commit and the send silently drops the notification forever, with no recovery. Legacy has
never had a story for that. The rewrite should — not because a PB entry demands it, but because
"fire-and-forget past the request" isn't actually good enough once you've already decided to make
this asynchronous; see WO-001.
