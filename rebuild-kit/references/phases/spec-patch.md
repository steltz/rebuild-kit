# Resume & Spec-Patch Mode

Entered when `rebuild.json` exists. Never regenerate a workspace over an existing one — the
root is an audited decision record; wholesale regeneration destroys rulings, ledger history,
and human sign-offs.

## Resume

`rebuild.json.status` + `phases_complete` say where generation stands; `ledger.json` says where
execution stands. Pick up at the first incomplete phase. If a workflow was interrupted, its
script is in `workflows/` — rerun it; the phase playbook's convergence criteria decide whether
its outputs count.

## Spec-patch — a human ruling arrived

Triggers: an ASK answered, an expected divergence approved/rejected, a problem-brief amendment,
an audit dispute resolved. The patch is a **targeted slice**, not a pipeline rerun:

1. **Record the ruling** at its source of truth: the OQ entry (ruling + who + when), the
   divergence manifest, or the PB register. Rulings are append-style — never erase the question
   or the losing reading; they're the decision record.
2. **Compute the blast radius**: which WOs cited the OQ/PB, which draft specs contain the
   affected claims, which contracts/fixtures encode the old reading, which replay sets and
   divergence entries are touched. Grep the workspace for the ID — citations make this cheap.
3. **Re-extract only the affected specs** (P4 procedure, scoped to the touched claims), update
   fidelity tags (an answered ASK usually becomes FIXED or REPAIR + divergence entry).
4. **Re-audit what was touched** (P9 procedure, scoped): falsification on the new claims only.
5. **Unblock the ledger**: clear `blocked_by_asks`, recompute risk scores for touched WOs
   (ASK density changed), set statuses back to `pending` where `awaiting_ruling`.
6. **Refresh the guide**: re-render affected chapters, `then-vs-now.md`, `decisions.md`
   (`scripts/render_guide.py` + narrative touch-up on changed sections only).
7. Commit the slice as one reviewable change: ruling + spec delta + ledger delta + guide delta.

Cheap, surgical regeneration is the point — rulings should propagate in minutes. If a ruling's
blast radius turns out to be "most of the workspace" (e.g. the target stack changed), stop and
tell the human what a re-run actually costs; that's a scope decision, not a patch.
