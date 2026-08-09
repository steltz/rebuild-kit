# P1 — Static Inventory

Outputs: `inventory.json`, `hotspots.md` (both at root level, referenced by later phases).

Deterministic extraction against the legacy dir at the pinned ref — this is script work, not
token work. The inventory is also **the enumeration the extraction workflows fan out over**
(P3–P5): if a module isn't in the inventory, no subagent will ever read it, so completeness here
is completeness everywhere.

## Procedure

```bash
python3 <skill>/scripts/inventory.py --root <rewrite-root>
```

The script produces: file tree with sizes/languages, module & dependency graph (import-level),
route/endpoint map (framework-pattern detection), DB schema dump (DDL files + migration dirs it
can find), per-file complexity approximation, and churn hotspots from git history.

Then apply judgment on top of the mechanical output:

1. **Spot-check the route map** against the actual code — pattern detection misses dynamically
   registered routes. Add any you find by reading entrypoints; mark them `detected: manual`.
2. **Verify the dependency graph is connected sensibly** — orphan modules are either dead code
   (candidate `do-not-port.md` entries — but demand evidence, e.g. zero inbound imports AND zero
   route references) or a detection gap.
3. **Write `hotspots.md`**: top files by churn × complexity, with one line each on why they're
   hot. These feed risk scores (P8) and audit priorities (P9).

## Degraded mode

No git history → churn is unavailable; complexity-only hotspots, note it in the file header.
Unsupported language → the script falls back to generic import-regex scanning; expect a sparser
graph and say so in `inventory.json.notes` — later phases must know the enumeration is weaker.

## Convergence

Every source file in the legacy tree appears in the inventory (the script asserts this); the
route map has been human-spot-checked (you); `hotspots.md` exists with ≥5 entries or an explicit
"small app, all files listed" note.
