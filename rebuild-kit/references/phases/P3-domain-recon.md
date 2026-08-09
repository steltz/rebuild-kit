# P3 — Architecture & Domain Recon

Outputs: `docs/00-overview.md` (system map, subsystem boundaries), `docs/domain/` (entities,
invariants, glossary).

This phase builds the shared vocabulary every later artifact uses. Subsystem boundaries drawn
here become the fan-out units for P4/P5 and the audit modules for P9; entity names fixed here
become the glossary the guide teaches.

## Procedure

1. From `inventory.json`, cluster modules into subsystems: follow the dependency graph's natural
   seams, route prefixes, and schema table groupings. Name each subsystem and record its member
   modules — this membership list **is** the P4/P5/P9 fan-out enumeration.
2. Write `docs/00-overview.md`: one-paragraph system description, a subsystem table (name,
   responsibility, member modules, routes, tables), a Mermaid dependency diagram between
   subsystems, and the external integration points (outbound calls, queues, cron).
3. For each significant entity: extract to `docs/domain/<entity>.md` — fields (from DDL +
   model code, cited), lifecycle/state machine if one exists (cited), invariants
   (uniqueness, referential rules, business rules enforced in code — each with `file:line`).
4. `docs/domain/glossary.md`: domain terms as the code uses them, including where code
   vocabulary conflicts with user vocabulary (those conflicts are ASK material).

## Workflow shape (larger targets)

Fan out one subagent per subsystem cluster to draft its overview row + entity files; converge by
cross-checking boundary claims — two subagents claiming the same module, or an inter-subsystem
call neither documented, is a boundary error to resolve before P4. Serial fallback: walk
subsystems in dependency order yourself.

## Evidence discipline

Invariants are the trap: code *suggests* invariants, only enforcement *proves* them. A DB
constraint is evidence; a validation in one of three write paths is an ASK ("enforced on create,
not on import — intended?"). Cite the enforcement site, not just the shape.
