# **Slugging** (how it works today)

The entire mechanism is `app/util.py`, three lines of logic: lowercase, collapse any run of
non-alphanumeric characters to a single hyphen, strip leading/trailing hyphens, truncate to 64
characters. The function's own comment names the bug: "collisions possible: two tickets named
'Fix DB' and 'fix db!' share a slug." There's no uniqueness check anywhere — not in the app, not
as a database constraint. A title made entirely of symbols (`"!!!"`) produces an *empty* slug,
which is arguably a worse version of the same problem, silently accepted because `NOT NULL`
doesn't reject empty strings (found during the adversarial audit, `audit/report.md`).

PB-003 names this as a known problem without naming a fix — "nobody has decided yet what the
fix should be" is the literal framing from leadership. That decision (reject and ask the
client to disambiguate? auto-suffix? fold the ticket id into every slug?) is still open —
`docs/open-questions.md` OQ-001.
