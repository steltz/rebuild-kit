# Harbor spike: eval-0 on Harbor with container isolation

**Date:** 2026-08-09
**Status:** Approved (design review in session), pending spec review
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
   image simply never contains the skill) replaces the seatbelt profile *for the spike*, but the
   spirit of `verify_isolation.py` is ported: a pre-flight probe must prove the leak vectors are
   closed before any paid trial, and the guard hook still polices remote retrieval.
3. **Success bar:** score parity with iteration-2 (Sonnet 5 executor), not just mechanics.
4. **Arm modeling:** Approach A — one task, two custom agent variants extending Harbor's
   Claude Code adapter (chosen over per-arm task directories and over a run_arm.py wrapper).

## Design

### 1. Layout

```
rebuild-kit-workspace/harbor-spike/
  eval-0/                      # the Harbor task
    instruction.md
    task.toml
    environment/Dockerfile     # + fixture bundle staged for build
    tests/                     # test.sh + grading wrapper (verifier-only)
  harbor_spike/                # Python package
    agents.py                  # Baseline, WithSkill agent classes
    report.py                  # fold Harbor trial rewards into parity table
  verify_container_isolation.py
  SPIKE-REPORT.md              # written at the end
```

### 2. Task definition

- `instruction.md` = eval-0 prompt from `evals.json` + the `AUTONOMY_FRAMING` block **verbatim**
  from `run_arm.py`. No skill suffix — that is arm-specific and therefore the agent's job.
  Rationale: iterations 1–2 comparability depended on this framing; drift here invalidates parity.
- `environment/Dockerfile`: python-slim + git; the `ticketd` fixture is restored **from its git
  bundle at image build time** so the container carries a live `.git` (grade_checks' legacy_ref
  pin check and the eval's git-HEAD assertion both need it). In-container path is neutral
  (`/app/work/ticketd`): nothing in path names or files hints a skill exists (preserves the
  no-breadcrumbs rule from RUN-PROTOCOL.md).
- `task.toml`: resource caps (cpus/memory_mb), agent + verifier `timeout_sec`, and
  `[verifier.environment]` with `environment_mode = "separate"` so `tests/` and the assertion
  set never enter the agent container.

### 3. Agents (the arms)

Two subclasses of Harbor's Claude Code adapter in `harbor_spike/agents.py`, selected with
`harbor run --agent`:

- **Baseline:** stock adapter behavior; model pinned to Sonnet 5; session persistence off.
- **WithSkill:** same, plus (a) uploads the skill tree into the container at agent-setup time at
  a neutral path, and (b) appends the `WITH_SKILL_SUFFIX` ("A skill that may help with this task
  is installed at {path}…") to the instruction. This is the container-era equivalent of the
  seatbelt profile's skill-subtree re-allow.

Both arms stage `guard_hook.py` into the container and wire it as a PreToolUse hook in the
in-container Claude settings: remote retrieval of the public `steltz/rebuild-kit` GitHub repo
stays blocked and audited, exactly as today.

### 4. Grading

- `tests/test.sh` calls a thin wrapper around the **unmodified** `grade_checks.py` and writes
  `reward.json` with one named 0/1 metric per assertion plus the aggregate.
- Multi-key rewards require a custom per-dimension metric config (Harbor's default `mean` metric
  handles single-key only — cookbook multi-reward recipe is the template).
- The verifier image carries `grade_checks.py` and the eval-0 assertion set; the agent container
  never does.
- **Known unknown, resolved empirically first:** how the agent's workdir is surfaced to a
  *separate* verifier environment. No published source documents this. If separate-mode
  verification cannot see the work product, fallback is same-container verification with
  assertions uploaded only at verify time — record whichever holds in SPIKE-REPORT.md.

### 5. Isolation verification

`verify_container_isolation.py`, run before any paid trial:

- **Static probe:** scan the built baseline image filesystem for skill markers (SKILL.md, known
  script names, spec-patch strings); assert `evals.json` and prior-iteration outputs are absent
  from **both** images (the with-skill image legitimately contains the skill, never the
  assertions); assert the task config declares no host bind-mounts.
- **Live probe:** one cheap trial with a canary prompt; assert the guard-hook audit log is
  non-empty. (This exact silent-hook failure bit the seatbelt harness once; the check is
  non-negotiable.)
- **Residual risk (stated, accepted):** the container has network access for the Anthropic API,
  so the public GitHub repo is reachable in principle; the guard hook polices the tool-call
  paths to it, same as today. No new exposure vs. the seatbelt harness.

### 6. Runs and parity

- Job: 10 trials/arm, Sonnet 5, `-n 4` local concurrency (Docker Desktop).
- `report.py` folds per-trial `reward.json` into an iteration-style comparison against
  iteration-2 eval-0 (with-skill 10/10, baseline 4/10).
- **Parity bar:** with-skill mean within 1 point of 10; baseline mean within 1.5 points of 4;
  discrimination gap ≥ 4 points preserved.
- Trials that die on infra errors (not agent failure) are rerun, not scored — same convention as
  `rerun_queue.sh`.

### 7. Deliverable

`SPIKE-REPORT.md`: parity table; answers to the four research open questions (arm modeling,
fixture injection pattern, isolation equivalence, separate-verifier mechanics); Harbor rough
edges encountered; go/no-go recommendation for migrating evals 1–2.

## Error handling

- Docker daemon down → fail fast with a clear message before any Harbor invocation.
- Image build failure (bundle restore, network) → surfaced verbatim; nothing scored.
- Trial timeout → recorded as an unscored infra failure and queued for rerun, distinguished from
  an agent that ran and produced a bad workspace (scored normally).
- Isolation probe failure → hard stop; no paid trials run.

## Testing

- `verify_container_isolation.py` must pass before the first paid trial (mirrors the
  RUN-PROTOCOL.md gate).
- Grading wrapper unit-checked against a copied iteration-2 output tree: wrapped
  `grade_checks.py` must reproduce that run's known per-assertion results byte-for-byte
  before any Harbor trial is graded with it.
- Harbor's Oracle sanity-check agent is skipped: eval-0 has no `solution/` and building one is
  out of scope.

## Out of scope (YAGNI)

Cloud backends; evals 1 and 2; RL/GEPA integration; replacing `generate_review.py`; any change
to the seatbelt harness, `evals.json`, or the skill itself.

## Open questions carried into implementation

1. Separate-verifier workdir visibility (see §4).
2. Whether Harbor's Claude Code adapter exposes settings/hook injection cleanly, or the agent
   subclass must write the in-container settings file itself.
3. Exact Harbor version to pin (pre-1.0, fast-moving; pin whatever `uv tool install harbor`
   resolves to at implementation time and record it in SPIKE-REPORT.md).
