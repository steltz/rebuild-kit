# Template: modern/CLAUDE.md

Generated from the problem brief's goals and the human's stack choice, so FREE decisions land
consistently. If the stack is undecided, ship the file with the PENDING marker — it makes the
blocker visible in every executor session.

```markdown
# <modern_dir>/ — Target Application

## Target stack  <!-- decided by: <FILL: human name> · <date> — or: PENDING (blocks P8/M0) -->
- Language/runtime: <FILL>        - Framework: <FILL>
- Database: <FILL>                - Key libraries: <FILL>
- Rationale: <FILL: one line, tied to brief goals (PB-nnn citations where they apply)>

## Architecture rules
<FILL: derived from brief goals & grievances — e.g. "PB-021 (untestable monolith): all IO
behind interfaces; no framework types in domain logic". Each rule cites its motivation.>

## Conventions
<FILL: layout, naming, error-handling shape, logging, test layout — the decisions FREE
implementations should not re-litigate per-WO.>

## What this file is not
Not a spec. Behavior comes from work orders and contracts; this file only governs HOW code is
written here. On conflict, the WO wins and the conflict is an open-questions.md entry.
```
