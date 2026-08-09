# internal-export (how it works today — and why it probably shouldn't tomorrow)

`GET /internal/export/csv` dumps every ticket as three-column CSV. Its own source comment
says it was "written for the 2020 audit; no caller since" (`ticketd/app/server.py:112`),
and the 30-day access log shows zero hits (`zero-traffic.md`). It is slated **do-not-port**
(DNP-001) — but a 30-day window can't see an *annual* audit tool, so the drop needs a
human ruling: **OQ-003** (`guide/briefs/OQ-003-ruling-brief.md`).

If the ruling is "keep": note the CSV assembly doesn't quote fields, so a ticket title
containing a comma or newline breaks the row format (`ticketd/app/server.py:114`) — the
keep-ruling must also decide bug-for-bug fidelity vs repair.
