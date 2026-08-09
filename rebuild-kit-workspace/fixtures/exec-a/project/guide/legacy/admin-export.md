# **Admin/Export** (how it works today)

One route, `GET /internal/export/csv`: dumps every ticket's id/title/status as CSV, no auth, no
params, no escaping (a title containing a comma corrupts the row). Its own code comment says
"written for the 2020 audit; no caller since," and it shows zero hits in the sampled access
log. Both are weak evidence on their own — the log only actually covers a synthetic 1-hour
window despite being described as a 30-day log (see the orientation chapter) — so this is
carried as a low-confidence do-not-port *candidate*, not a confirmed one
(`docs/do-not-port.md` DNP-002, `docs/open-questions.md` OQ-004). It stays in the backlog as a
low-priority, last-in-line work order until someone who knows whether the 2020 audit process
still exists can rule on it.
