# Do Not Port

<!-- Negative space. Each entry: what, evidence (zero-traffic + zero-references / PB-nnn), provenance. -->

## `app/legacy_import.py` — 2019 spreadsheet importer
- what: `import_spreadsheet(path)`, a one-off CSV importer for the pre-2019 spreadsheet era.
- evidence: zero-references confirmed — the module's own docstring states "Nothing imports this
  module," and a repo-wide grep of `legacy/` confirms no import sites. Zero-traffic could NOT be
  confirmed (P2/runtime evidence is inactive — no access logs).
- provenance: generator P0/P3 static read; tracked as OQ-006 (pending ruling) rather than a hard
  exclusion, since the zero-traffic half of the evidence bar is unavailable. Default: do not
  port into `modern/`. Revisit if OQ-006 is ruled otherwise, or once log access (OQ-007) confirms
  zero-traffic.

## Trailing no-op comments in `app/server.py`
- what: `# tweak 1` / `# tweak 2` / `# tweak 3` at `legacy/app/server.py:120-122`, after
  `if __name__ == "__main__":`. No associated code change, no git history to explain them.
- evidence: zero semantic content — cosmetic cruft, not a behavior.
- provenance: generator P0 static read. Not worth an OQ; simply not carried into `modern/`.
