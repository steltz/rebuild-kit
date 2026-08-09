# Review: Harbor eval-0 spike spec + plan

**Reviewed:** 2026-08-09, four parallel adversarial lenses (spec-plan consistency, internal plan correctness, architecture soundness, codebase grounding against Harbor 0.20.0 source and the repo).
**Spec:** `docs/superpowers/specs/2026-08-09-harbor-spike-design.md`
**Plan:** `docs/superpowers/plans/2026-08-09-harbor-spike.md` (unbuilt at review time)

## Scores

- **Spec: 5/10.** The architecture and decisions are sound and traceable, but the parity bar — the document's core success criterion — is stated on a scale the spike never measures (finding 2), one §3 requirement would break the adapter if implemented (15), and four smaller wording/model errors would mislead a literal reader (21–24).
- **Plan: 2/10** (rubric-clamped; raw deductions exceed the scale). The cross-task consistency work is genuinely clean — every load-bearing name, path, key, and constant survives task-to-task, and the Harbor-facts block is fully accurate against 0.20.0 source. The risk is concentrated in one theme: **the isolation gate verifies artifacts that are not the artifacts trials actually use** (findings 1, 3, 4, 6, 13), plus a contaminating breadcrumb leak (1), an unshaken with-skill arm ahead of the paid run (5), and a Task 6 built on the wrong network knob (7). Most fixes are small; the count is what sinks the score.

What checked out clean (verified, not assumed): `WITH_SKILL_SUFFIX`/`AUTONOMY_FRAMING` byte-identical to `run_arm.py`; guard hook env-var contract; `grade_checks.py` CLI/stdout shape; fixture HEAD `1cc1135`; iteration-2 layout incl. `mechanical_checks.json` shape; `graft` CLI; all Harbor API signatures the plan relies on (`render_instruction` dispatch reaches the CLI prompt, `artifacts = ["/app/work"]` validates, separate-verifier artifact re-materialization, trial dirs flat under the job dir, reward/result filenames); no name drift across the 9 tasks.

---

## Critical

**1. Guard hook + settings.json leak skill breadcrumbs into the baseline container; the gate is structurally blind to it.**
*Plan Task 3 + Task 4; spec §3/§5.*
`guard_hook.py` is uploaded verbatim into both arms. Its docstring, regexes (`github\.com[:/][\w.-]+/rebuild-kit`, `rebuild.kit`, `render_guide`), and deny message name the skill and where it lives; `settings.json` (agent-readable, in the bind-mounted logs dir) carries `RK_GUARD_MODE=block`. A baseline agent reading its own config dir — normal behavior — learns a skill named rebuild-kit exists on GitHub. Violates the plan's own neutral-naming Global Constraint and biases the arm. The static probe can never catch it: it greps the image; the hook and settings are runtime uploads that happen after the probe.
**Fix:** ship a sanitized in-container hook (neutral docstring/deny text, patterns decoded from obfuscated constants at runtime, `WSVC_*` env names); add a host test asserting the uploaded payloads contain no marker strings; extend the live probe to grep a fully set-up container, not just the image.

## High

**2. Parity reference scale mismatch between spec and plan — the verdict can flip depending on which doc you trust.**
*Spec §6; plan Task 7 (`iteration2_reference`, `parity_verdict`, test).*
Spec anchors ("with-skill 10/10, baseline 4/10") are `grading.json` expectation counts (verified). The spike grades mechanically: `mechanical_checks.json` has **11** checks — with_skill 10 true / 1 false, without_skill **3 true / 2 null / 6 false**. `iteration2_reference()` computes 3.0; the spec's bar is |x−4|≤1.5; the plan's implemented bar is |x−3|≤1.5; the synthetic test hardcodes 4.0, masking the divergence. With-skill threshold (9.0) is meanwhile hardcoded from the spec scale.
**Fix:** pin the bar to the mechanical scale explicitly in both docs (baseline ref 3/11 with 2 nulls, with-skill ref 10/11), compute both references from stored `mechanical_checks.json`, have the report print both scales with nulls called out.

**3. The gate verifies stale images Harbor never runs.**
*Plan Tasks 1/4/5/8.*
`task.toml` declares no `docker_image`, so Harbor builds its own image from `eval-0/environment/` at trial time; the gate probes the manually tagged `wsvc-ev0:local` from Task 1. Both launch sequences run `prepare_task.py` (restaging context) → verify → `harbor run` with **no rebuild between** — the gate certifies the previous context. Same class: the verifier image bakes a `grade_checks.py` snapshot (the file has uncommitted modifications right now), host tests validate the host copy, and nothing checks image freshness — 20 paid trials could grade with stale semantics.
**Fix:** the gate itself rebuilds both images (or compares `sha256sum` of in-image `grade_checks.py`/`tests/*` against host copies) before probing; record image IDs into the job dir at launch.

**4. No per-trial validity sentinels: two silent-corruption paths score as normal trials.**
*Plan Tasks 7/8; spec §5 calls the live hook check "non-negotiable" yet it runs once, baseline-only.*
(a) A partial artifact transfer of `/app/work` degrades gracefully in `grade_checks.py` — mechanics failure scores as a low-reward agent trial, shifting the baseline mean inside the tolerance. (b) A guard hook that stops firing after Task 5–6 config churn produces unaudited trials that score normally; the Task 8 gate is static-only.
**Fix:** `run_grading.py` asserts an artifact sentinel (pinned-HEAD `ticketd/.git` reachable under `/app/work`) and emits **no reward.json** on failure (→ infra failure → rerun); `collect_trials` marks any scored trial with a missing/empty `agent/guard_audit.jsonl` invalid, and the verdict refuses to pass with invalid trials present.

**5. The with-skill arm's first live execution is inside the paid 20-trial job.**
*Plan Task 5 (baseline-only shakedown) + Task 8.*
`upload_dir` copy-into vs copy-as ambiguity: if the skill lands at `/opt/wsvc-kit/rebuild-kit/SKILL.md`, the suffix's promised path is empty, the arm silently behaves like baseline, and 10 paid trials produce a parity FAIL misattributed to Harbor. The FakeEnv test only records the call tuple. (Also: uploading the repo dir as-is could plant the literal name `rebuild-kit` in-container.)
**Fix:** add one with-skill shakedown trial with explicit checks — `test -f /opt/wsvc-kit/SKILL.md` during setup (fail loudly), suffix visible in the agent transcript, audit-mode log non-empty.

**6. The gate blocks itself: the "rebuild-kit" grep runs against the verifier image, whose grader contains that string.**
*Plan Task 4 Step 3.*
`probe_image` unconditionally greps `/grader` (among others) for `rebuild-kit`; `grade_checks.py`'s docstring contains it. `verify_container_isolation.py` always exits nonzero on a correctly built verifier image → every gated run (paid or not) is blocked and `test_passes_on_clean_images` fails.
**Fix:** parameterize the grep phase per image; grep the agent image fully, and for the verifier image drop `/grader`/`/tests` from targets (it legitimately holds the grader, never the skill).

**7. Task 6's allowlist recipe uses the wrong knob and would fail every attempt.**
*Plan Task 6.*
`AgentConfig.extra_allowed_hosts` merges into the policy **during `agent.run()` only** (`harbor/models/trial/config.py:119-125`); the ClaudeCode install curls `downloads.claude.ai` during `setup()` (`claude_code.py:177-190`), which runs under the environment baseline — allowlist with zero hosts as written. All 3 timeboxed attempts fail at install; a false "allowlist doesn't work" finding gets recorded. Two aggravators: egress control is only enforced with Linux kernel support (`docker.py:188-195` — verify under Docker Desktop first), and the success criterion has no true negative probe (an ignored `network_mode` would still "pass").
**Fix:** put install/API hosts in task.toml `[environment] allowed_hosts` (or job-level `environment.extra_allowed_hosts`); pre-check egress support on Docker Desktop; verify success with an in-container `curl https://github.com` asserting failure.

## Medium

**8. Task 6 is scope the spec never approved, inserted between shakedown and parity run.**
*Plan Task 6 vs spec §5 ("residual risk … accepted") .*
It changes the measured environment after mechanics validation and spends an unapproved paid trial; an intermittently-blocking allowlist would distort the 20-trial run.
**Fix:** move Task 6 after the parity run (or behind the Task 8-style user gate), and require parity to run with whichever config the last shakedown validated.

**9. Rerun trials are unreachable by the report; retry could exceed the approved budget.**
*Plan Task 8 Steps 1/4/5; Task 7.*
Manual reruns land in different job dirs; `report.py` takes one `--job-dir`. "Rerun, not scored" degrades to "dropped." `retry.max_retries: 2` worst-cases 60 paid trials against a 20-trial approval, and its trigger conditions (agent timeout vs infra) are unverified.
**Fix:** `report.py` accepts multiple `--job-dir`s and asserts scored+infra counts per arm sum to 10; state a max total-trial budget in the user gate; confirm retry triggers from source first.

**10. Arm-name lookup mismatch produces a garbage verdict; the test masks it.**
*Plan Task 7 + both job yamls.*
With only `import_path` set, real `config.json` has `"name": null` (`set_default_name`, `trial/config.py:171-175`); the fallback yields `RkBaseline`/`RkWithSkill`, while `parity_verdict` looks up `rk-baseline`/`rk-with-skill` → empty arms, means 0.0. The synthetic test writes `"name": "rk-with-skill"`.
**Fix:** add `name: rk-baseline` / `name: rk-with-skill` to the yaml agent entries; make `parity_verdict` raise if an expected arm key is absent; mirror the null-name shape in the test.

**11. `_stage_arm`'s manifest parsing is wrong on every assumption and no-ops silently.**
*Plan Task 2 Step 5.*
Real manifest: `{bundle_filename: {head_branch, head_sha, path}}` with `__`-separated keys; no `"bundle"` key; the bundle file is `_git_bundles/<key>`. The filter matches nothing, the `if bundle and target.exists()` guard skips every graft, trees grade without `.git`, and the regression failure misdirects toward "wrapper changes grading semantics."
**Fix:** filter/relativize on `meta["path"]`, graft `_git_bundles/<key>`, and `assert grafted > 0` per arm.

**12. The task directory name `eval-0` leaks into agent-visible container identity.**
*Plan Task 1 layout vs the neutral-naming Global Constraint.*
Harbor derives trial/container names from the task name; `hostname` or `/etc/hostname` tells the agent it's in an eval. No probe checks it.
**Fix:** rename the task dir neutrally (`wsvc-0/`), and add a shakedown check grepping hostname/env for `eval|skill|rebuild`.

**13. `MARKERS` uses exact `find -name` matching — a leaked `grade_checks.py` passes the gate.**
*Plan Task 4 Step 3.*
`-name "grade_checks"` doesn't match `grade_checks.py`; `-name "rebuild-kit"` only matches a file literally so named.
**Fix:** globs — `"grade_checks*"`, `"*rebuild-kit*"`.

**14. The bind-mount assertion is vacuous and checks the wrong layer.**
*Plan Task 4 `check_task_toml`; spec §5.*
Task-level `EnvironmentConfig` has no `mounts`/`volumes` fields (they're job/trial-level: `trial/config.py:213`), so the check can never fire while the real vector (job.yaml `environment.mounts`) is unchecked.
**Fix:** validate via Harbor's own models; assert on the job yamls' `environment.mounts` instead.

**15. Spec §3 "session persistence off" is unimplemented — and implementing it would break the adapter.**
*Spec §3; plan Task 3.*
No task turns it off; per source, stock `ClaudeCode.run()` requires the session JSONL under `CLAUDE_CONFIG_DIR` for trajectory/cost accounting — a literal implementer following the spec would break Harbor's accounting.
**Fix:** reword spec §3 to "session persistence left at adapter default (Harbor consumes the session JSONL); trial containers are fresh per trial, which is the isolation the seatbelt flag provided."

## Low

**16. Task 2 Step 4's crash contingency contradicts the Step 1 test** (all-0.0 fallback can't produce per-check keys the test asserts). Fix: emit a `grader_error: 0.0` sentinel key in that branch and say the test changes.
**17. `setup()` is never exercised by host tests; `@override` gives no runtime signal.** A signature mismatch first surfaces in the paid shakedown. Fix: host test calling `setup()` against FakeEnv or `inspect.signature` compatibility check.
**18. Static probe gaps vs spec §5:** verifier image not probed for `evals.json`; neither image probed for prior-iteration markers (`mechanical_checks.json`, `grading.json`). Fix: extend both probe lists.
**19. Fixture staged from the live working tree; spec said bundle-restore.** A dirty `fixtures/ticketd` bakes uncommitted edits into both arms. Fix: `git status --porcelain` cleanliness assertion in `prepare_task.py` (or restore from the bundle as specced) and record the deviation.
**20. Python floor wrong:** plan says 3.11+; Harbor requires ≥3.12 (`Requires-Python`) and `typing.override` is 3.12+. Self-correcting at install time, but stalls. Fix: `uv venv --python 3.12` and say 3.12+.
**21. Spec §4's "default `mean` metric handles single-key only" is false in 0.20.0** (`metrics/base.py:14-35` aggregates per-key). Fix: drop the sentence (the plan bypasses job metrics anyway).
**22. Spec §5 describes a "with-skill image" that doesn't exist under Approach A** (one shared image; skill uploaded at setup). Fix: reword to "agent image and verifier image"; the with-skill exception applies to the running container post-setup.
**23. Spec §3 wording implies both arms block;** actual (and correct, matching `run_arm.py`) is baseline=block, with-skill=audit. Fix: one clause stating per-arm modes.
**24. Spec's out-of-scope list names `generate_review.py`, which doesn't exist in the repo** (no grep hit outside the spec). Fix: name the real artifact or drop the bullet.

---

## Application status

**User selected: all. Applied 2026-08-09** — spec rewritten in place; plan rewritten as v2 (task renumbering: report generator is now Task 6, parity run Task 7, and the allowlist experiment moved post-parity as Task 8).

| # | Finding | Status | How |
|---|---|---|---|
| 1 | Guard-hook breadcrumb leak | applied | Sanitized `wsvc_policy.py` + base64 `.dat` patterns generated by `prepare_task.py`; `WSVC_*` env names; neutral deny text; `test_container_payloads_sanitized` enforces |
| 2 | Parity reference scale mismatch | applied | Spec §6 re-pinned to mechanical scale (10/11, 3/11, 2 nulls); `references()` computes both refs from stored files; report prints both scales |
| 3 | Gate probes stale images | applied | Gate is build-then-probe; records image IDs; Task 7 forbids mid-job rebuilds and archives IDs |
| 4 | No per-trial validity sentinels | applied | Artifact sentinel in `run_grading.py` (no reward file on failure → infra); `collect_trials` classifies empty-audit trials invalid; verdict blocks PASS on any invalid |
| 5 | With-skill arm unshaken | applied | Task 5 shakedown runs both arms with arm-specific checks; `upload_skill` verifies/repairs layout in-code and raises loudly |
| 6 | Gate self-blocks on verifier grep | applied | Per-image probe scoping; verifier grep excludes `/grader` and `/tests` |
| 7 | Allowlist on wrong knob | applied | Hosts moved to task.toml `[environment] allowed_hosts` (covers install phase); egress-support pre-check; canary negative probe task |
| 8 | Allowlist perturbs parity env | applied | Moved post-parity (Task 8), optional, own user gate |
| 9 | Reruns unreachable / retry budget | applied | `report.py` accepts multiple `--job-dir` + per-arm accounting assertion; user gate states worst-case 60 executions; `include_exceptions` restricted to infra errors |
| 10 | Arm-name null verdict | applied | `name:` set in both job yamls; `_arm_name` normalizes; `parity_verdict` raises on missing arm; test mirrors null-name shape |
| 11 | `_stage_arm` manifest parsing | applied | Rewritten to verified schema (`meta["path"]`, key = bundle filename) with `assert grafted > 0` |
| 12 | `eval-0` name leaks into container identity | applied | Task dir renamed `wsvc-0`; shakedown checks container names + in-container hostname/env |
| 13 | Exact-name markers | applied | Glob markers (`grade_checks*`, `*rebuild-kit*`, …) |
| 14 | Vacuous mounts check | applied | Check moved to job-yaml layer (`environment.mounts`), where Harbor accepts mounts |
| 15 | Session persistence requirement | applied | Spec reworded: adapter default kept (Harbor consumes session JSONL); fresh containers provide the isolation |
| 16 | Crash contingency vs test | applied | `grader_error: 0.0` sentinel key; test accepts either shape |
| 17 | `setup()` untested | applied | `test_setup_and_render_signatures_match_base` (inspect.signature) |
| 18 | Probe marker gaps | applied | `evals.json` + prior-iteration markers (`mechanical_checks*`, `grading.json`, `benchmark.json`) on both images |
| 19 | Fixture dirty-tree risk | applied | `check_fixture_clean()` porcelain assertion; deviation recorded in spec §2 and plan self-review notes |
| 20 | Python floor | applied | `uv venv --python 3.12`; tech-stack line corrected |
| 21 | Stale mean-metric claim | applied | Spec sentence replaced; correction noted in plan self-review notes |
| 22 | "With-skill image" wording | applied | Spec §5 reworded (agent image + verifier image; skill uploaded into the running container) |
| 23 | Guard-mode wording | applied | Spec §3 states per-arm modes (baseline strict/blocks, with-skill monitor/audits) |
| 24 | `generate_review.py` reference | applied | Spec out-of-scope now says "the iteration review viewer tooling" |
