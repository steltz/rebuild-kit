# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

## DNP-001 — `legacy/app/legacy_import.py` (`import_spreadsheet()`)

- **What:** a one-off CSV importer for the 2019 spreadsheet migration. Module docstring:
  "Nothing imports this module."
- **Evidence:** zero inbound imports (`grep -rn legacy_import legacy/` finds no reference to the
  module anywhere outside the file itself) **and** zero route references (not wired to any Flask
  route, not called from `server.py`). This meets P1's evidence bar for dead code (zero inbound
  imports AND zero route references — see `hotspots.md`).
- **Caveat:** P2 (runtime evidence) is inactive, so this is static evidence only — there is no
  log/cron confirmation that it isn't invoked some other way (a manual `python -c` one-liner,
  a cron job outside this repo, etc.). Static dead-code evidence is strong for a module this
  small and self-contained (7 lines, stdlib `csv` only, no side effects beyond a file read), but
  the caveat is recorded per the evidence-or-it-doesn't-ship rule.
- **Provenance:** P1 static inventory, confirmed P3 domain recon (`docs/00-overview.md`). Not
  from human testimony — nobody reported this; it's a static finding, hence do-not-port rather
  than a PB-driven removal.
- **Disposition:** excluded from the rewrite. No WO ports it. If evidence later surfaces that
  something outside this repo depends on it, that's new information — bring it back through
  spec-patch, not silently.
