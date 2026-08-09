# Executor final report — eval-1 with_skill (Sonnet 5, isolated rerun)

Applied the OQ-002 ruling as a targeted spec-patch (per references/phases/spec-patch.md), committed as f7e4693.
- Ruling recorded at source: docs/open-questions.md OQ-002 ruling filled (Dana, dated); docs/problem-brief.md PB-003 UNDISPOSITIONED -> REPAIR in WO-002.
- Blast radius: WO-002's conflated ASK statement split into FIXED (unchanged truncation mechanics) + REPAIR (uniqueness/suffix rule) linked to new ED-002; expected-divergences.yaml gains ED-002; ledger.json WO-002 unblocked; guide decisions/then-vs-now/orientation re-rendered via scripts/render_guide.py (mechanical sections only, no hand-editing).
- Scoped re-audit (P9-lite) caught a REAL gap, then fixed: legacy server.py:51,55 calls slugify(title) independently for the DB insert and the API response — harmless while pure, but once slug generation is stateful (uniqueness-aware), a second independent call could see its own just-written row and append a spurious extra suffix, making stored and returned slugs disagree. Added a REPAIR statement requiring the slug be computed once and reused.
- Left correctly unresolved (not invented): whether the suffix counts against the 64-char cap and the double-hyphen edge case — flagged FREE (outcome required, mechanism open) since Dana's ruling doesn't specify.
- docs/contracts/ddl.sql intentionally untouched (P5: verbatim legacy schema; a UNIQUE constraint belongs in a future P6 migration-target schema, which doesn't exist yet — noted as a forward obligation worth a PB/OQ entry when P6 runs).
- Unrelated placeholder sections (CLAUDE.md, backlog.md, hotspots.md FILL markers) out of scope, untouched.
