# P10 — The Field Guide

Outputs: `guide/` tree. Runs after the audit so it teaches only claims that survived.

The secondary goal, structurally separated so it can never dilute the primary one: the guide is
a **generated projection** of the same evidence base into human-readable form — narrative,
diagrams, progressive depth. Same citations, same fidelity tags, same confidence; open
questions appear as exactly that — open. Never hand-forked: a correction belongs in the spec,
and the guide re-renders from it.

## Structure

```
guide/
├── 00-orientation.md    # the 10-minute tour: what this system is, the map, where to start
├── legacy/              # how the legacy app works: per-subsystem chapters, narrative + diagrams
├── modern/              # how the new app will work; fills in as-built as milestones close
├── flows/               # end-to-end storyboards: sequence diagram + an annotated real trace
├── then-vs-now.md       # per subsystem: what changes (REPAIR/PB), what holds (FIXED), what's open
├── decisions.md         # readable changelog: divergence manifest + rulings, with rationale
├── glossary.md          # domain vocabulary from recon
└── briefs/              # just-in-time: ruling briefs (OQ-*) and gate packets (WO-*)
```

## Procedure

1. Run the mechanical assembly first: `python3 <skill>/scripts/render_guide.py --root <root>`
   — it builds ledger-derived tables, `decisions.md` from the divergence manifest, and chapter
   skeletons with citations pulled from the audited specs.
2. Write the narrative layers on the skeletons:
   - **Legacy chapters**: the how-it-works story per subsystem — architecture narrative, main
     flows, and the archaeology ("why is it like this"), with the weirdness explained through PB
     entries and code evidence.
   - **Modern chapters**: start as-designed from target architecture; marked `designed-not-built`
     until milestones close and as-built content fills in from the ledger.
   - **Flow storyboards**: reuse the replay corpus as teaching material — a sequence diagram
     beside a real captured trace, annotated step by step. An actual password reset walking
     through the system beats any prose description.
3. **Honesty rules**: teach nothing beyond the audited spec; surface confidence and degraded-
   mode caps explicitly; mark unbuilt sections as designed-not-built.

## Just-in-time briefs — education inside the workflow

Wire into root CLAUDE.md (P8 already scaffolds this; verify): when the executor files an ASK it
generates a **ruling brief** — the question, the evidence for each reading, affected flows,
options with consequences — one page, everything needed to rule well without opening the legacy
tree. When a gate WO halts, it emits a **gate packet**: what the WO does, its risk drivers, what
to inspect, the relevant traces. Templates: `templates/ruling-brief.md`, `templates/gate-packet.md`.

## Lifecycle

Generated in P10; regenerated when rulings patch specs and when milestones close. The
markdown-plus-Mermaid tree is canonical; an optional rendered handbook (HTML/PDF) can be
produced for distribution outside the repo.

## Workflow shape

Per-chapter parallel rendering from the audited artifacts; briefs and packets generated on
demand during execution. Guide regeneration must stay cheap — that's why it actually happens.
