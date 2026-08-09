# Discarded iteration-3 attempts (API connection drops)

Three arms died on "API Error: Connection closed mid-response" while 8 sessions
ran concurrently. They are kept for the record but excluded from grading and from
the benchmark, and they live outside `iteration-3/` because both the aggregator
and the eval viewer discover runs by walking for any directory containing
`outputs/` — left in place, these were picked up as runs with no eval metadata.

They were re-run rather than graded because the drops cost real work, not just
the closing report:

- eval-0 with_skill  — 94 turns, no backlog and no harness produced
- eval-0 without_skill — errored
- eval-2 with_skill (x2) — reached only P4 of 11 phases (`status: generating`)

Grading these would have understated the skill. The replacements are all
`is_error: false` and phase-complete.
