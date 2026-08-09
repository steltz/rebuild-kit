# Hotspots

<!-- Degraded mode: the legacy tree shipped with no git history (see rebuild.json.legacy_pin_note).
     The raw "churn" numbers inventory.py reported are an artifact of this workspace's own fresh
     git init (it counted line-adds in the P0 scaffold commit, not real legacy change history) —
     they are not legacy churn and are dropped here entirely. Ranking below is complexity- and
     evidence-only, per P1's degraded-mode rule. Small app: all 5 legacy files are listed. -->

| file | loc | complexity | why it's hot |
|---|---|---|---|
| app/server.py | 122 | 29 | Entire application: 7 routes, all business logic, both known defects (PB-001 synchronous email at lines 76 & 94, PB-002 MD5 token at line 90), plus several code-observed oddities logged as PB-proposals (undocumented rate-limit bypass header at line 84, non-standard 200-with-empty-body on missing ticket at line 63, naive local time at line 52). Highest-risk single file by a wide margin — every WO but the migration WOs touches it. |
| app/notify.py | 7 | 0 | Small but load-bearing: the synchronous SMTP call PB-001 targets. Complexity score is 0 (no branches) but risk is high — it's the mechanism, not the logic, that's the defect. |
| app/util.py | 7 | 0 | `slugify()` has a known collision property (two distinct titles can produce the same slug — no uniqueness constraint on `tickets.slug` in the DDL). Not reported by the human, so it stays FIXED pending a PB-proposal ruling (`docs/open-questions.md`), but it's worth a human's eyes because it's cheap to fix and easy to miss. |
| app/legacy_import.py | 7 | 0 | Zero inbound references anywhere in the tree (`grep -rn legacy_import legacy/` returns nothing but the route/comment declaring it dead) and zero route registrations — meets the do-not-port evidence bar. See `docs/do-not-port.md`. |
| db/schema.sql | 22 | 0 | 3 tables, no migrations directory (none exists — this is the only schema definition). `reset_tokens` has no primary key and no uniqueness constraint on `token`; feeds P6 census generation once DB access exists. |
