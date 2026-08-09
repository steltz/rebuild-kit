# Hotspots

<!-- Degraded mode: no git history came with the handover, so churn is unavailable for every
     file (— in the churn column). Ranking is complexity + judgment only. Small app: all 5
     files listed; the enumeration for P3–P5 is this whole table. -->

| file | loc | complexity | churn | why it's hot |
|---|---|---|---|---|
| app/server.py | 122 | 29 | — | The entire app: all 7 routes, DB access, rate limiting, token logic; both PB defects' call sites; every load-bearing quirk (200-on-missing, priority coercion, bypass header) lives here |
| app/notify.py | 7 | 0 | — | PB-001 root cause: blocking SMTP with 30s timeout inside request threads; hardcoded host |
| db/schema.sql | 22 | 0 | — | Migration source of truth; CHECK constraints define the priority/status vocabularies; reset_tokens has no PK/index and stores plaintext tokens (PB-002) |
| app/util.py | 7 | 0 | — | slugify: shared by ticket creation; own comment admits slug collisions — behavior question for the rewrite (OQ-003) |
| app/legacy_import.py | 7 | 0 | — | Cold, not hot: zero inbound imports, zero routes, docstring says one-off 2019 importer — do-not-port candidate DNP-001 |
