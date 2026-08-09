# Harbor spike: eval-0 on Harbor with container isolation

**Date:** 2026-08-09
**Status:** Approved; amended 2026-08-09 after adversarial review (all findings applied — see
`docs/superpowers/plans/2026-08-09-harbor-spike-review.md`)
**Decision context:** Deep-research assessment of Harbor (run `wf_213bcdf3-4ef`, report at
claude.ai/code/artifact/522e7e54-78db-4bd3-bfed-179f044f7f90) recommended a hybrid adoption —
Harbor for execution/scaling, custom grading and arm logic retained — gated on a hands-on spike
answering four open questions no published source covers.

## Goal

Convert **eval-0 only** (ticketd full-generation) to a Harbor task and run both arms through
Harbor on local Docker, to produce a go/no-go decision for migrating the rest of the
rebuild-kit eval harness. The existing seatbelt harness (`evals/isolation/run_arm.py`) stays
untouched and remains the harness of record until the spike passes.

## Decisions made during brainstorming

1. **Scope:** spike first, not full migration. One eval, both arms, local Docker only.
2. **Isolation stance:** container-only + verification. Absence-by-construction (the baseline
   container simply never contains the skill) replaces the seatbelt profile *for the spike*, but
   the spirit of `verify_isolation.py` is ported: a pre-flight gate must prove the leak vectors
   are closed before any paid trial, and a policy hook still polices remote retrieval.
3. **Success bar:** score parity with iteration-2 (Sonnet 5 executor), not just mechanics.
4. **Arm modeling:** Approach A — one task, two custom agent variants extending Harbor's
   Claude Code adapter (chosen over per-arm task directories and over a run_arm.py wrapper).

## Design

### 1. Layout

```
rebuild-kit-workspace/harbor-spike/
  wsvc-0/                      # the Harbor task (neutral name: the task dir name
    instruction.md             #   becomes container identity the agent can see)
    task.toml
    environment/Dockerfile     # + fixture staged into build context
    tests/                     # test.sh + grading wrapper (verifier-only)
  harbor_spike/                # Python package
    agents.py                  # RkBaseline, RkWithSkill agent classes
    report.py                  # fold Harbor trial rewards into parity report
    wsvc_policy.py             # sanitized in-container policy hook (see §5)
  verify_container_isolation.py
  SPIKE-REPORT.md              # written at the end
```

### 2. Task definition

- `instruction.md` = eval-0 prompt from `evals.json` + the `AUTONOMY_FRAMING` block **verbatim**
  from `run_arm.py`. No skill suffix — that is arm-specific and therefore the agent's job.
  Rationale: iterations 1–2 comparability depended on this framing; drift here invalidates parity.
- `environment/Dockerfile`: python-slim + git; the `ticketd` fixture (whose live `.git` was
  bundle-restored) is staged from `fixtures/ticketd` into the build context, guarded by a
  `git status --porcelain` cleanliness assertion inside the fixture repo so uncommitted fixture
  edits can never silently bake into the agent image. In-container path is neutral
  (`/app/work/ticketd`): nothing in path names, files, hostnames, or container names hints a
  skill or an eval exists (preserves the no-breadcrumbs rule from RUN-PROTOCOL.md).
- `task.toml`: resource caps (cpus/memory_mb), agent + verifier `timeout_sec`, and
  `[verifier.environment]` with `environment_mode = "separate"` so `tests/` and the grading
  code never enter the agent container.

### 3. Agents (the arms)

Two subclasses of Harbor's Claude Code adapter in `harbor_spike/agents.py`, selected with
`harbor run --agent`:

- **RkBaseline:** stock adapter behavior; model pinned to Sonnet 5. Session persistence is left
  at the adapter's default — Harbor consumes the session JSONL under `CLAUDE_CONFIG_DIR` for
  trajectory and cost accounting, so disabling it would break the adapter; the isolation that
  `run_arm.py --no-session-persistence` provided is supplied structurally by fresh per-trial
  containers instead.
- **RkWithSkill:** same, plus (a) uploads the skill tree into the container at agent-setup time
  at a neutral path, verifying post-upload that `SKILL.md` is present where the prompt says it
  is, and (b) appends the `WITH_SKILL_SUFFIX` ("A skill that may help with this task is
  installed at {path}…") to the instruction. This is the container-era equivalent of the
  seatbelt profile's skill-subtree re-allow.

Both arms stage a **sanitized** policy hook (see §5) as a PreToolUse hook: remote retrieval of
the public skill repo is policed exactly as today, with per-arm modes mirroring `run_arm.py` —
baseline **blocks** (strict), with-skill **audits only** (monitor).

### 4. Grading

- `tests/test.sh` calls a thin wrapper around the **unmodified** `grade_checks.py` and writes
  `reward.json` with one named 0/1 metric per assertion plus the aggregate. Harbor's job-level
  metrics are deliberately bypassed; the report reads per-trial `reward.json` directly.
- The wrapper first asserts an **artifact sentinel** — the fixture's pinned git HEAD is
  reachable under the transferred workdir — and emits *no* reward file when the sentinel fails,
  so a broken artifact transfer surfaces as an infrastructure failure (rerun), never as a
  low-scoring agent trial.
- The verifier image carries `grade_checks.py` and the tests; the agent container never does.
- **Resolved from Harbor 0.20.0 source (verified, not assumed):** in separate-verifier mode the
  agent workdir crosses via task-level declared artifacts, re-materialized at the same absolute
  path, and the verifier image must already contain `/tests` (Harbor skips uploading them).

### 5. Isolation verification

`verify_container_isolation.py`, run before any paid trial:

- **Build-then-probe:** the gate itself rebuilds both images from the current build contexts
  before probing, so the certified bytes are the bytes trials run (a probe of a stale sibling
  image certifies nothing), and it records the resulting image IDs for the run record.
- **Static probe:** scan the agent image and the verifier image for skill markers, assertion
  files, and prior-iteration output markers (glob-matched, not exact-name). The with-skill
  arm's skill content is uploaded into its *running container* at setup — there is no
  "with-skill image" — so the image probes apply to both arms' shared agent image; the verifier
  image legitimately holds the grader (never the skill). Host bind-mounts are checked at the
  layer where Harbor actually accepts them (job-level environment config), not just task.toml.
- **Sanitized runtime payloads:** everything the agents upload at runtime (policy hook, its
  pattern data, settings) must be free of skill-naming strings — the hook's detection patterns
  ship encoded and decode only in memory, its docstring and deny message are neutral, and a
  host-side test enforces this. Rationale: the original `guard_hook.py` names the skill and its
  repo in plaintext; uploading it verbatim would hand the baseline arm the exact breadcrumb
  trail this design exists to remove, invisibly to any image-level probe.
- **Live probe:** the shakedown runs **both arms** once before the parity batch, checking the
  policy audit log is non-empty per arm, the with-skill container really has the skill at the
  promised path, and container names/hostnames/env carry no eval/skill breadcrumbs. Per-trial
  audit-log presence is additionally re-checked across the paid batch at report time; a scored
  trial with a missing or empty audit log is classified invalid and blocks a parity PASS.
- **Residual risk (stated, accepted):** the container has network access for the Anthropic API,
  so the public GitHub repo is reachable in principle; the policy hook polices the tool-call
  paths to it, same as today. No new exposure vs. the seatbelt harness. An **optional,
  post-parity** hardening experiment may attempt Harbor's `network_mode = "allowlist"` to make
  this enforcement-grade; it runs only after the parity measurement (never between shakedown
  and parity, so the measured environment stays fixed), behind its own user cost gate.

### 6. Runs and parity

- Job: 10 trials/arm, Sonnet 5, `-n 4` local concurrency (Docker Desktop).
- The report folds per-trial `reward.json` into a comparison against iteration-2 eval-0.
- **Parity bar — pinned to the mechanical scale, the only scale the spike measures.**
  Iteration-2's stored `mechanical_checks.json` for eval-0 has 11 checks: with-skill 10 true /
  1 false; baseline 3 true / 2 null / 6 false (nulls score 0 mechanically). Bar: with-skill
  mean within 1.0 of the stored with-skill mechanical total (10); baseline mean within 1.5 of
  the stored baseline mechanical total (3); discrimination gap ≥ 4.0. Both references are
  *computed from the stored files*, never hardcoded. For context only: iteration-2's
  analyst-graded scores were 10/10 vs 4/10 (`grading.json`) — a different scale that includes
  human judgment of the mechanical nulls; the report prints both scales side by side.
- Trials that die on infra errors (not agent failure) are rerun, not scored; rerun trials'
  job dirs are included in the report's inputs, and the report asserts per-arm accounting
  (scored + infra + invalid = expected trials).

### 7. Deliverable

`SPIKE-REPORT.md`: parity table (both scales); answers to the four research open questions
(arm modeling, fixture injection pattern, isolation equivalence, separate-verifier mechanics);
Harbor rough edges encountered; image IDs and pinned versions; go/no-go recommendation for
migrating evals 1–2.

## Error handling

- Docker daemon down → fail fast with a clear message before any Harbor invocation.
- Image build failure (staging, network) → surfaced verbatim; nothing scored.
- Trial timeout → recorded as an unscored infra failure and queued for rerun, distinguished from
  an agent that ran and produced a bad workspace (scored normally).
- Artifact-transfer failure → no reward file emitted (sentinel) → infra failure, rerun.
- Isolation probe failure → hard stop; no paid trials run.

## Testing

- `verify_container_isolation.py` must pass before every paid launch (mirrors the
  RUN-PROTOCOL.md gate), and it rebuilds what it certifies.
- Grading wrapper unit-checked against a copied iteration-2 output tree: wrapped
  `grade_checks.py` must reproduce that run's known per-assertion results exactly before any
  Harbor trial is graded with it.
- Runtime-payload sanitization is enforced by a host-side test, not convention.
- Harbor's Oracle sanity-check agent is skipped: eval-0 has no `solution/` and building one is
  out of scope.

## Out of scope (YAGNI)

Cloud backends; evals 1 and 2; RL/GEPA integration; replacing the iteration review viewer
tooling; any change to the seatbelt harness, `evals.json`, or the skill itself.

## Open questions carried into implementation

1. Whether the Claude Code CLI honors a `settings.json` placed in `CLAUDE_CONFIG_DIR`
   (fallback: the agent user's `~/.claude/settings.json`) — resolved empirically in shakedown.
2. Whether Docker Desktop on this host supports Harbor's egress control at all
   (`network_mode` enforcement is Linux-kernel-gated in 0.20.0) — checked before the optional
   allowlist experiment.
3. Exact Harbor version pin: 0.20.0 (verified against source throughout; recorded in
   SPIKE-REPORT.md alongside the claude CLI version the adapter installs).
