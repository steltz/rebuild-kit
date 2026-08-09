# Known defect: eval-3 assertion 5 is mis-targeted

Assertion as written:
  "Implemented behavior honors the workspace's documented fidelity decisions:
   the missing-ticket 200-empty-body response is preserved, and email dispatch
   no longer blocks the request."

Problem, found by the eval-3 with_skill grader: those two behaviors belong to
work orders (WO-002, WO-006) that the skill-generated backlog deliberately
defers behind the WO-001 walking skeleton. An executor that correctly scopes
itself to the first work item therefore CANNOT satisfy the assertion, while an
executor that ignores the plan and implements everything would pass it. It
rewards exactly the behavior the eval is meant to penalize.

It also compares unequally: the two arms' workspaces sequence work differently,
so the assertion asks each arm about behaviors its own plan may not have
scheduled yet.

Correct form (apply before any future iteration):
  "Within the scope it undertook, the implementation contradicts none of the
   workspace's documented fidelity decisions; behaviors deferred to later work
   items are left unimplemented rather than guessed at."

That is scope-relative, gradeable from the delta, and penalizes both silent
deviation and premature implementation.

Not retro-fixed in iteration-3: the runs are already graded against the assertion
as written, and rewriting it after seeing results would be fitting the measure to
the outcome. Iteration-3 reports it as a failure for both arms and discounts it
in the analysis instead.
