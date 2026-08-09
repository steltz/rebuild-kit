# Traffic analysis: `ticketd/ops/access.log`

Derived by direct analysis of the log (`awk`/`grep` over all 2,000 lines).
Reproduce with the commands inline below — nothing here required guessing.

## Important caveat — read before trusting this data

The task description refers to this as "a ~30-day access log." **It is not.**
Every one of the 2,000 lines falls on a single calendar date
(`12/Jul/2026`), inside a single 60-minute window (`10:00:00`–`10:59:59`),
with timestamps that increment in an unnaturally regular `SS:SS` pattern
(`10:00:00`, `10:01:01`, `10:02:02`, ...). There is exactly one client
identity (`jdoe@corp.example.com`) and one user agent (`svc-ui/2.1`) across
every single line.

```
$ grep -oE '\[[0-9]+/[A-Za-z]+/[0-9]+' ops/access.log | sort -u
[12/Jul/2026        # only one distinct date in the file
$ awk '{print $3}' ops/access.log | sort -u
jdoe@corp.example.com   # only one identity
$ awk -F'"' '{print $6}' ops/access.log | sort -u
svc-ui/2.1              # only one user agent
```

**Conclusion: this is a synthetic/sampled single-hour, single-client log, not
a real 30-day production capture.** Treat every number below as directional
evidence of *endpoint mix and error shape*, not as a real capacity/traffic
baseline. **Do not size infrastructure, rate limits, or SLAs off these raw
numbers without pulling the real 30-day log from production first** — this
is called out again in `03-OPEN-QUESTIONS.md`.

## Endpoint mix (2,000 requests total)

| Endpoint | Count | % of traffic |
|---|---:|---:|
| `GET /api/tickets` | 1,235 | 61.75% |
| `POST /api/tickets` | 423 | 21.15% |
| `GET /api/tickets/:id` | 184 | 9.20% |
| `POST /api/tickets/:id/close` | 99 | 4.95% |
| `POST /api/auth/reset` | 39 | 1.95% |
| `POST /api/auth/reset/confirm` | 20 | 1.00% |
| `GET /internal/export/csv` | 0 | 0% |

Reproduce:
```
awk -F'"' '{print $2}' ops/access.log | awk '{print $1, $2}' \
  | sed -E 's#/api/tickets/[0-9]+#/api/tickets/:id#; s#/internal/export.*#/internal/export/csv#' \
  | sort | uniq -c | sort -rn
```

**Implication for the rewrite:** the system is read-dominated (61.75% is a
single unpaginated list endpoint). Whatever the new stack does, `GET
/api/tickets` needs to stay cheap — this is the endpoint most likely to
regress if an ORM introduces N+1 queries or an unnecessary join. It's also
the endpoint most exposed if pagination semantics change (see
`01-CURRENT-BEHAVIOR-CONTRACT.md` — pagination must remain opt-in).

## Status codes

| Status | Count | % |
|---|---:|---:|
| 200 | 1,948 | 97.4% |
| 500 | 51 | 2.55% |
| 429 | 1 | 0.05% |

Reproduce: `awk '{print $9}' ops/access.log | sort | uniq -c`

The 500s are not clustered in time (they're spread roughly evenly across the
sampled hour, 1-4 per minute-bucket) — i.e. **this log does not capture the
June SMTP outage** (that would show as a sustained burst of slow closes, not
scattered 500s). The scattered 500s are consistent with the known
`priority` validation bug (see behavior contract §2, `POST /api/tickets`):
any client sending an out-of-enum `priority` value trips the SQLite `CHECK`
constraint and gets an uncaught 500. Since 500s appear on `GET /api/tickets`
and `GET /api/tickets/:id` too, not just `POST`, there may be a second,
unidentified source of 500s — **flagged as open**, not something this log
sample can diagnose (no error bodies are logged, only status/size/duration).

## Latency

All requests in the sample complete in well under 1 second (slowest observed:
0.364s, a `POST /api/tickets/:id/close`). The 10 slowest requests skew toward
`close` and `reset`/`reset/confirm` — consistent with those being the three
endpoints that call `send_mail()` synchronously. This sample was presumably
captured while the SMTP path was healthy — it does **not** contain evidence
of the multi-second-to-30-second stalls the June outage produced, since
`smtplib.SMTP(..., timeout=30)` in `app/notify.py` would show up as ~30s
outliers if SMTP were down during capture.

**Net: use this log for endpoint mix and error-shape evidence. Do not use it
as evidence about the outage itself, and do not use it as a real capacity
baseline** — pull the actual 30-day log before load-testing the new service
(see `03-OPEN-QUESTIONS.md`, item 1).
