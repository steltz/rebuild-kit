# P0 — Intake & Scaffold

Outputs: `rebuild.json`, root `CLAUDE.md`, `docs/problem-brief.md`, the full directory layout,
the legacy pin + read-only guard, seed entries for `do-not-port.md` and NFR targets.

## 1. Locate the legacy tree

You run one directory above the legacy application. Identify the legacy subdirectory (ask if
ambiguous — e.g. multiple app-looking dirs). If the session was opened *inside* the legacy repo,
propose creating the rewrite root as its parent and moving/cloning accordingly; never scaffold
workspace files into the legacy tree itself.

## 2. The intake interview

Do this **before** any code analysis, so observed defects don't get enshrined as `FIXED`.
Capture, with an ID (`PB-nnn`), provenance (who reported, severity, affected area):

- **Motivation** — why rewrite, why now.
- **Known defects** — bugs users live with; each needs a reproduction or affected area.
- **Pain points** — performance, reliability, operability, UX complaints.
- **Architectural grievances** — where the current design fights change.
- **Target goals & constraints** — scale, SLOs, team shape, operability; these become NFR targets.
- **Non-goals** — improvements explicitly out of scope for this rewrite.

Also collect in the same conversation: the **target stack** decision (human's call — record
`pending` if undecided; it blocks P8's modern/CLAUDE.md content, nothing earlier), and what
**runtime evidence** exists (logs, APM, analytics, prod DB access) plus PII-scrubbing approval.

Interview style: concrete follow-ups ("what breaks most often?", "what would you be embarrassed
to show a new hire?"), not a form dump. If the user provided a brief, docs, or ticket exports
up front, harvest them into PB entries and confirm only the gaps. Non-interactive runs: harvest
what was given, record remaining gaps as open intake questions inside the brief, continue.

Write `docs/problem-brief.md` from `templates/problem-brief.md`. Every entry starts
`disposition: UNDISPOSITIONED` — P8/P9 are responsible for closing them all out.

Entries marked "must not survive the rewrite" seed `docs/do-not-port.md` immediately, with the
PB ID as provenance. Goals with measurable targets seed the NFR list in the brief.

## 3. Scaffold the root

Run the bundled scaffolder — don't hand-create the tree:

```bash
python3 <skill>/scripts/scaffold.py --root <rewrite-root> --legacy-dir <name> [--modern-dir modern]
```

It creates the layout from `references/schema.md`, writes `rebuild.json` (pinning `legacy_ref`
to the legacy HEAD SHA), installs the pre-commit hook that rejects any diff under the legacy
dir, initializes the root git repo, and drops CLAUDE.md skeletons at the root and in `modern/`.

Then **fill the skeletons** — the scaffolder leaves `<FILL>` markers:
- Root `CLAUDE.md` from `templates/root-claude-md.md`: layout map, roles, read/write rules,
  executor loop, gate + escalation protocol.
- `modern/CLAUDE.md` from `templates/modern-claude-md.md`: target stack + conventions if decided,
  else a visible "stack: PENDING (blocks P8)" marker.

Record in `rebuild.json.evidence` which evidence subsystems are active vs inactive, with notes —
this is the degraded-mode ledger the whole pipeline reads.

## Convergence

P0 is done when: `rebuild.json` validates against the schema; `git -C <root> log` shows the
initial commit; a write under `legacy/` is actually rejected by the hook (test it); and the
problem brief has ≥1 entry per section the user gave testimony for, all with IDs and provenance.
