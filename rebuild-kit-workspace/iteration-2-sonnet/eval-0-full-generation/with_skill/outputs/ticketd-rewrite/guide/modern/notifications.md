# **Notifications** (designed-not-built)

Not implemented yet — see `docs/features/WO-002-async-notification-dispatch.md`, the WO PB-001
exists to close. Designed outcome: no request handler performs mail-transport I/O
synchronously; ticket-close and reset-request return promptly and correctly regardless of SMTP
health. Mechanism (in-process background task vs. a durable queue/outbox) is an open FREE
choice pending confirmation of how strong a delivery guarantee is actually needed
(`docs/open-questions.md` OIQ-1 in the problem brief) — default recommendation is the simpler
in-process option first, upgradeable later. Recipient and message content for both call sites
are unchanged.
