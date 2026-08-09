# **(dead) Import** (how it works today)

`app/legacy_import.py` is seven lines — a CSV reader for the 2019 spreadsheet-to-database
migration. Its own docstring says "Nothing imports this module," and the static inventory
confirms it: zero inbound references anywhere in the tree. This is the one module in the app
with genuinely high-confidence dead-code evidence (as opposed to `admin-export.md`'s weaker,
traffic-based case) — see `docs/do-not-port.md` DNP-001. Not part of the rewrite.
