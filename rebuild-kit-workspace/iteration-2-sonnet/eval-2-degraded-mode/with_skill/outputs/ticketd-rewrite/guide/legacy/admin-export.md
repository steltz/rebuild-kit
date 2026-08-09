# Admin / Export (how it works today)

One route, `GET /internal/export/csv` (`legacy/app/server.py:111-115`), dumping every ticket as
a 3-column CSV (`id,title,status` — notably NOT the other five columns). A comment says it was
"written for the 2020 audit; no caller since." That comment is not proof the route is dead —
nobody has run access logs against it (`rebuild.json.evidence.runtime_ingestion = inactive`), so
this is exactly the "zero-traffic ≠ dead" trap the skill's evidence discipline warns about. It's
routed, it's reachable, it stays in the rewrite (`WO-005`) unless a human decides otherwise.

Small implementation wart worth knowing: the CSV is built with a raw f-string join, no quoting
or escaping — a title containing a comma would produce malformed output. Nobody reported this as
a problem, so it's not a REPAIR; but it's exactly the kind of thing a normal, idiomatic
implementation (using Python's `csv` module instead of legacy's hand-rolled join) fixes as a
side effect without anyone having to make it a special decision — see `WO-005`'s FREE-choice
note.
