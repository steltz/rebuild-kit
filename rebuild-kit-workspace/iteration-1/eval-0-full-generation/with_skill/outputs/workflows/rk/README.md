# Vendored rebuild-kit runtime scripts (skill_version 1.0)

The executor session has no skill installed, so the scripts the workspace depends on at
execution time are vendored here, verbatim:

- `replay.py` — L3 comparator (used by `verification/harness/diff-run.sh`)
- `render_guide.py` + `rk_common.py` — guide refresh at milestone close
- `staleness_check.py` — report upstream legacy drift vs the pin

Treat as read-only tooling; fixes belong upstream in the skill.
