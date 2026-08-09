# internal-export (how it works today — if it's alive at all)

`GET /internal/export/csv` (`ticketd/app/server.py:111-115`): every ticket as
`id,title,status` lines — three columns despite the `SELECT *`, no escaping (a comma in a
title corrupts the row), no auth, insertion order. The comment says it was "written for the
2020 audit; no caller since."

We cannot prove it dead: there are no access logs in this handover (degraded mode), so
zero-traffic can't be shown. This is **OQ-001**, it blocks WO-007, and the owner can
probably answer it from memory in one sentence. If ruled dead, DNP-002 activates and the
route vanishes; if ruled live, the format — broken escaping included — is frozen, because
whatever parses it has parsed exactly this since 2020.
