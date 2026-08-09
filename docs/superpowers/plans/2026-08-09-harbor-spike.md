# Harbor Eval-0 Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

*Amended 2026-08-09: all 24 findings from `2026-08-09-harbor-spike-review.md` applied. Task order changed from v1: the network-allowlist experiment is now Task 8 and runs only AFTER the parity run.*

**Goal:** Run eval-0 (ticketd full-generation), both arms, through Harbor 0.20.0 on local Docker with container isolation, and produce a parity verdict against iteration-2-sonnet.

**Architecture:** One Harbor task (`wsvc-0/`) shared by both arms; the arms are two subclasses of Harbor's `ClaudeCode` adapter (baseline = stock, with-skill = uploads the skill at setup and appends the prompt suffix). Grading wraps the unmodified `grade_checks.py` in a separate verifier container, guarded by an artifact sentinel; the agent workdir crosses via Harbor's declared-artifacts mechanism. The isolation gate rebuilds what it certifies, and every runtime payload uploaded into agent containers is sanitized of skill-naming strings.

**Tech Stack:** Harbor 0.20.0 (pinned in a local venv; **requires Python ≥ 3.12** — `Requires-Python` in its metadata, and the code uses 3.12 features), Docker Desktop, pytest for host tests, Claude Code CLI in-container (installed by the adapter).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-09-harbor-spike-design.md` (amended). Repo root: `/Users/nicholasstelter/Code/skills/rebuild-kit` (call it `$REPO`). Spike root: `$REPO/rebuild-kit-workspace/harbor-spike` (call it `$SPIKE`).
- **Do not modify:** `grade_checks.py`, `evals.json`, anything under `$REPO/rebuild-kit/` (the skill), or `evals/isolation/` (seatbelt harness). The spike only adds files under `$SPIKE` and these docs.
- Venv: `$SPIKE/.venv` created with `uv venv --python 3.12` (or newer), `harbor==0.20.0` + `pytest`. Run the CLI as `$SPIKE/.venv/bin/harbor`, host tests as `$SPIKE/.venv/bin/python -m pytest`. Custom agents load via `PYTHONPATH=$SPIKE`.
- Executor model for paid runs: `claude-sonnet-5` (matches iteration-2-sonnet).
- **Neutral naming rule** (from RUN-PROTOCOL.md), now including runtime artifacts: nothing visible to the agent container may hint that a skill or eval exists — the task directory is `wsvc-0` (its name becomes container/hostname identity), images use the `wsvc` prefix, the skill mounts at `/opt/wsvc-kit`, the in-container hook is `wsvc_policy.py` with encoded patterns, and the strings "skill", "rebuild-kit", "eval", "guard" must not appear in any agent-visible file, env var, or path. A host test enforces this for uploaded payloads.
- Harbor facts verified from 0.20.0 source (do not "correct" them from docs): reward file is `/logs/verifier/reward.json` (singular), flat `{str: float}`; trial result file is `result.json` (singular); trial dirs sit directly under the job dir, each with `config.json`; in separate-verifier mode the verifier image must already contain `/tests` and the agent workdir arrives only via task-level `artifacts` entries re-materialized at the same absolute path; `artifacts = ["/app/work"]` validates as-is; `AgentConfig.extra_allowed_hosts` applies **only during `agent.run()`** — the install phase runs under the `[environment]` baseline policy; egress control is enforced only with Linux kernel support (`environments/docker/docker.py:188-195`).
- Fixture ground truth: `$REPO/rebuild-kit-workspace/fixtures/ticketd` has a live `.git`; HEAD is `1cc113597ea87990e731f02190fc6999e42e7cd8`.
- **Paid-run budget:** Task 5's shakedown = 2 trials (one per arm). Task 7's parity batch = 20 trials, worst case 60 agent executions with `retry.max_retries: 2`; the user gate must state this and get explicit approval. Task 8's allowlist experiment = up to 4 additional cheap trials, behind its own user gate. No paid run starts unless `verify_container_isolation.py` passed in the same session.
- Commits: semantic messages, no AI attribution trailers.

---

### Task 1: Spike venv, task directory, agent image

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/.gitignore`
- Create: `rebuild-kit-workspace/harbor-spike/prepare_task.py`
- Create: `rebuild-kit-workspace/harbor-spike/wsvc-0/task.toml`
- Create: `rebuild-kit-workspace/harbor-spike/wsvc-0/environment/Dockerfile`
- Generated (never committed): `wsvc-0/instruction.md`, `wsvc-0/environment/context/ticketd/`, `harbor_spike/_generated/wsvc_policy.dat`

**Interfaces:**
- Produces: agent Docker image `wsvc-ev0:local` with the fixture at `/app/work/ticketd` (live `.git`); `wsvc-0/instruction.md` = eval prompt + AUTONOMY_FRAMING verbatim; validated `task.toml` with `environment_mode = "separate"` and `artifacts = ["/app/work"]`; encoded policy patterns at `harbor_spike/_generated/wsvc_policy.dat`.
- Consumes: `fixtures/ticketd`, `evals/evals.json` (read-only), `evals/isolation/run_arm.py` and `evals/isolation/guard_hook.py` (imported for constants/patterns).

- [ ] **Step 1: Create the venv (Python ≥ 3.12) and pin Harbor**

```bash
mkdir -p /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python "harbor==0.20.0" pytest
.venv/bin/python -c "import sys, harbor; assert sys.version_info >= (3,12); print('harbor ok')"
```
Expected: `harbor ok`.

- [ ] **Step 2: Write `.gitignore`**

```gitignore
.venv/
wsvc-0/environment/context/
wsvc-0/instruction.md
harbor_spike/_generated/
verifier/_ctx/
jobs/
__pycache__/
scratch/
```

- [ ] **Step 3: Write `prepare_task.py`**

```python
#!/usr/bin/env python3
"""Stage generated task inputs: instruction.md, the fixture build context, and
the encoded policy patterns.

Regenerates from source-of-truth (evals.json + run_arm.py + guard_hook.py) so
the Harbor task can never drift from the seatbelt harness's framing, and so no
plaintext skill-naming string ever needs to be committed for container use.
"""
import base64
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
WORKSPACE = SPIKE.parent
FIXTURE = WORKSPACE / "fixtures" / "ticketd"
TASK = SPIKE / "wsvc-0"
CONTEXT = TASK / "environment" / "context"
GENERATED = SPIKE / "harbor_spike" / "_generated"

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def check_fixture_clean():
    r = subprocess.run(["git", "-C", str(FIXTURE), "status", "--porcelain"],
                       capture_output=True, text=True, check=True)
    if r.stdout.strip():
        raise SystemExit(
            f"fixtures/ticketd working tree is dirty — refusing to stage "
            f"uncommitted fixture state into the agent image:\n{r.stdout}")

def write_instruction(run_arm):
    evals = json.loads((WORKSPACE / "evals" / "evals.json").read_text())
    ev = next(e for e in evals["evals"] if e["id"] == 0)
    (TASK / "instruction.md").write_text(ev["prompt"] + run_arm.AUTONOMY_FRAMING + "\n")

def stage_fixture():
    if CONTEXT.exists():
        for p in CONTEXT.rglob("*"):          # fixture legacy trees can be read-only
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
        shutil.rmtree(CONTEXT)
    CONTEXT.mkdir(parents=True)
    shutil.copytree(FIXTURE, CONTEXT / "ticketd", symlinks=True)
    head = subprocess.run(["git", "-C", str(CONTEXT / "ticketd"), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    print(f"staged ticketd at HEAD {head}")
    return head

def generate_policy_dat(guard_hook):
    # guard_hook.py holds the detection patterns as module-level constants.
    # Read the file first and confirm the constant names; the assertion below
    # fails loudly if they change. Patterns ship base64-encoded so the strings
    # never appear in plaintext inside the agent container.
    patterns = []
    for attr in dir(guard_hook):
        val = getattr(guard_hook, attr)
        if attr.isupper() and isinstance(val, (list, tuple)) and \
           all(isinstance(x, str) for x in val) and val:
            if any("rebuild" in x or "render_guide" in x or "skill" in x.lower()
                   for x in val):
                patterns.extend(val)
    assert patterns, "no pattern constants found on guard_hook — read the file and fix the extraction"
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "wsvc_policy.dat").write_text(
        "\n".join(base64.b64encode(p.encode()).decode() for p in patterns) + "\n")
    print(f"encoded {len(patterns)} policy patterns")

def main():
    check_fixture_clean()
    run_arm = load_module("run_arm", WORKSPACE / "evals" / "isolation" / "run_arm.py")
    guard_hook = load_module("guard_hook", WORKSPACE / "evals" / "isolation" / "guard_hook.py")
    write_instruction(run_arm)
    stage_fixture()
    generate_policy_dat(guard_hook)

if __name__ == "__main__":
    main()
```
**Before finalizing:** read `evals/isolation/guard_hook.py` (91 lines) and confirm how its patterns are stored (the grep hints at regex string constants around lines 27–30). If they live in a dict or single compiled list, replace the reflective loop in `generate_policy_dat` with a direct reference to the real constant name(s). The output contract is fixed: one base64-encoded regex per line in `wsvc_policy.dat`.

- [ ] **Step 4: Run it and verify the staged HEAD**

```bash
.venv/bin/python prepare_task.py
```
Expected: `staged ticketd at HEAD 1cc113597ea87990e731f02190fc6999e42e7cd8` and a nonzero pattern count. If the fixture repo is dirty, stop and resolve with the user — do not stage.

- [ ] **Step 5: Write `wsvc-0/environment/Dockerfile`**

```dockerfile
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates procps ripgrep \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/work
COPY context/ticketd /app/work/ticketd
WORKDIR /app/work
```
(The container's Python is only the task runtime — Harbor itself never runs inside it, so 3.11-slim is fine; `curl` + `ca-certificates` are what the ClaudeCode install bootstrap needs.)

- [ ] **Step 6: Write `wsvc-0/task.toml`**

```toml
schema_version = "1.3"

artifacts = ["/app/work"]

[agent]
timeout_sec = 3600.0

[verifier]
timeout_sec = 900.0
environment_mode = "separate"

[verifier.environment]
docker_image = "wsvc-ev0-verifier:local"

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
workdir = "/app/work"
```

- [ ] **Step 7: Validate task.toml against Harbor's own parser**

```bash
.venv/bin/python - <<'EOF'
from pathlib import Path
from harbor.models.task.config import TaskConfig
from harbor.models.task.verifier_mode import resolve_task_verifier_mode
cfg = TaskConfig.model_validate_toml(Path("wsvc-0/task.toml").read_text())
print("verifier mode:", resolve_task_verifier_mode(cfg))
print("artifacts:", cfg.artifacts)
EOF
```
Expected: verifier mode SEPARATE; artifacts includes `/app/work` (verified against 0.20.0: `artifacts: list[str | ArtifactConfig]` accepts plain strings).

- [ ] **Step 8: Build the agent image and probe it**

```bash
docker build -t wsvc-ev0:local wsvc-0/environment
docker run --rm wsvc-ev0:local git -C /app/work/ticketd rev-parse HEAD
docker run --rm wsvc-ev0:local sh -c 'find / \( -name "SKILL.md" -o -name "evals.json" \) -not -path "/proc/*" 2>/dev/null | head; echo probe-done'
```
Expected: HEAD `1cc1135...`; the find prints nothing before `probe-done`. (This is a smoke check only — the authoritative gate is Task 4, which rebuilds before probing.)

- [ ] **Step 9: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/.gitignore \
        rebuild-kit-workspace/harbor-spike/prepare_task.py \
        rebuild-kit-workspace/harbor-spike/wsvc-0/task.toml \
        rebuild-kit-workspace/harbor-spike/wsvc-0/environment/Dockerfile
git commit -m "feat(harbor-spike): wsvc-0 task definition and agent image"
```

---

### Task 2: Grading wrapper with artifact sentinel, verifier image, iteration-2 regression

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/wsvc-0/tests/run_grading.py`
- Create: `rebuild-kit-workspace/harbor-spike/wsvc-0/tests/test.sh`
- Create: `rebuild-kit-workspace/harbor-spike/verifier/Dockerfile`
- Test: `rebuild-kit-workspace/harbor-spike/tests_host/test_run_grading.py`

**Interfaces:**
- Consumes: `grade_checks.py --eval 0 --outputs DIR` printing exactly one JSON object `{check_name: {"ok": bool|null, "evidence": str}}` to stdout (verified).
- Produces: `/logs/verifier/reward.json` — flat float dict: one `1.0/0.0` key per check (null → `0.0`), plus `total` (count of true) and `unscoreable` (count of null); on grader crash, sentinel key `grader_error: 0.0` with `total: 0.0`. **On artifact-sentinel failure: no reward file at all** (Harbor then raises `RewardFileNotFoundError` → the trial records an exception → infra failure → rerun). Verifier image `wsvc-ev0-verifier:local` containing `/tests/`, `/grader/grade_checks.py`, and `/grader/expected_head`. Later tasks rely on these exact key names.

- [ ] **Step 1: Write the failing host tests**

`tests_host/test_run_grading.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parents[1]
RUN_GRADING = SPIKE / "wsvc-0" / "tests" / "run_grading.py"
IT2 = SPIKE.parent / "iteration-2-sonnet" / "eval-0-full-generation"
BUNDLES = SPIKE.parent / "iteration-2-sonnet" / "_git_bundles"
GIT_BUNDLES = SPIKE.parent / "evals" / "git_bundles.py"

def run_wrapper(outputs_dir: Path, reward_dir: Path, grader: Path, expected_head: str = ""):
    r = subprocess.run(
        [sys.executable, str(RUN_GRADING), "--outputs", str(outputs_dir),
         "--reward-dir", str(reward_dir), "--grader", str(grader),
         "--expected-head", expected_head],
        capture_output=True, text=True)
    return r, (reward_dir / "reward.json")

def test_reward_shape_on_empty_outputs(tmp_path):
    """Empty outputs, no sentinel required: grades all-fail, flat float dict."""
    outputs = tmp_path / "outputs"; outputs.mkdir()
    r, reward_path = run_wrapper(outputs, tmp_path, SPIKE.parent / "grade_checks.py")
    assert r.returncode == 0, r.stderr
    reward = json.loads(reward_path.read_text())
    assert all(isinstance(v, float) for v in reward.values())
    assert reward["total"] == 0.0
    assert "unscoreable" in reward
    per_check = {k: v for k, v in reward.items()
                 if k not in ("total", "unscoreable", "grader_error")}
    assert per_check or "grader_error" in reward

def test_sentinel_failure_writes_no_reward(tmp_path):
    """--expected-head set but no matching git tree => NO reward.json (infra failure)."""
    outputs = tmp_path / "outputs"; outputs.mkdir()
    r, reward_path = run_wrapper(outputs, tmp_path, SPIKE.parent / "grade_checks.py",
                                 expected_head="1cc113597ea87990e731f02190fc6999e42e7cd8")
    assert r.returncode != 0
    assert not reward_path.exists()

def _stage_arm(tmp_path, arm: str) -> Path:
    """Copy an iteration-2 arm's outputs and re-attach git history from bundles.

    Real manifest shape (verified): {bundle_filename: {"head_branch", "head_sha",
    "path"}} where keys are __-separated bundle filenames living in _git_bundles/
    and "path" is the /-separated repo location relative to the iteration dir.
    """
    import shutil, stat
    src = IT2 / arm / "outputs"
    dst = tmp_path / arm
    shutil.copytree(src, dst, symlinks=True)
    for p in dst.rglob("*"):
        p.chmod(p.stat().st_mode | stat.S_IWUSR)
    manifest = json.loads((BUNDLES / "manifest.json").read_text())
    prefix = f"eval-0-full-generation/{arm}/outputs/"
    grafted = 0
    for bundle_name, meta in manifest.items():
        path = meta["path"]
        if not path.startswith(prefix):
            continue
        target = dst / path[len(prefix):]
        assert target.exists(), f"manifest points at missing tree: {path}"
        subprocess.run([sys.executable, str(GIT_BUNDLES), "graft",
                        str(BUNDLES / bundle_name), str(target)], check=True)
        grafted += 1
    assert grafted > 0, f"no bundles grafted for {arm} — manifest parsing is broken"
    return dst

def test_matches_iteration2_mechanical_checks(tmp_path):
    for arm in ("with_skill", "without_skill"):
        outputs = _stage_arm(tmp_path, arm)
        r, reward_path = run_wrapper(outputs, tmp_path / f"reward-{arm}",
                                     SPIKE.parent / "grade_checks.py")
        assert r.returncode == 0, r.stderr
        reward = json.loads(reward_path.read_text())
        stored = json.loads((IT2 / arm / "mechanical_checks.json").read_text())
        for name, res in stored.items():
            expected = 1.0 if res.get("ok") is True else 0.0
            assert reward.get(name) == expected, (
                f"{arm}/{name}: wrapper={reward.get(name)} stored ok={res.get('ok')}")
```
**Before running:** sanity-check the assumed shapes with `ls "$IT2/with_skill/"` and `python3 -c "import json;[print(k, v) for k, v in list(json.load(open('$BUNDLES/manifest.json')).items())[:3]]"`. The manifest schema above was verified during review; if it differs, fix `_stage_arm` — the `assert grafted > 0` guarantees a parsing miss fails loudly instead of grading history-less trees.

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
.venv/bin/python -m pytest tests_host/test_run_grading.py -v
```
Expected: FAIL (run_grading.py does not exist).

- [ ] **Step 3: Write `wsvc-0/tests/run_grading.py`**

```python
#!/usr/bin/env python3
"""Wrap the unmodified grade_checks.py into Harbor's reward contract.

Order of operations matters:
1. Artifact sentinel: if --expected-head is set, the fixture git tree must be
   reachable under --outputs with that HEAD. On failure we exit nonzero WITHOUT
   writing reward.json, so Harbor records the trial as an infrastructure
   failure (rerun) instead of a low-scoring agent trial.
2. Grade: run grade_checks.py; null (not mechanically scoreable) counts 0.0 and
   is tallied in `unscoreable`. A grader crash yields grader_error=0.0 rather
   than no file — the environment was fine, the outputs were gradeable-empty.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

def find_fixture_head(outputs: Path) -> str | None:
    for git_dir in outputs.rglob("ticketd"):
        if (git_dir / ".git").exists():
            r = subprocess.run(["git", "-C", str(git_dir), "rev-parse", "HEAD"],
                              capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout.strip()
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--reward-dir", default="/logs/verifier")
    ap.add_argument("--grader", default="/grader/grade_checks.py")
    ap.add_argument("--expected-head", default="")
    args = ap.parse_args()
    outputs = Path(args.outputs)

    if args.expected_head:
        head = find_fixture_head(outputs)
        if head != args.expected_head:
            print(f"ARTIFACT SENTINEL FAIL: fixture head {head!r} != "
                  f"expected {args.expected_head!r} — treating as transfer failure; "
                  f"no reward written", file=sys.stderr)
            return 1

    proc = subprocess.run(
        [sys.executable, args.grader, "--eval", "0", "--outputs", str(outputs)],
        capture_output=True, text=True)
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    try:
        checks = json.loads(proc.stdout)
        reward = {name: (1.0 if res.get("ok") is True else 0.0)
                  for name, res in checks.items()}
        reward["total"] = float(sum(1 for r in checks.values() if r.get("ok") is True))
        reward["unscoreable"] = float(sum(1 for r in checks.values() if r.get("ok") is None))
    except (json.JSONDecodeError, AttributeError):
        reward = {"grader_error": 0.0, "total": 0.0, "unscoreable": 0.0}

    out = Path(args.reward_dir) / "reward.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reward, indent=1))
    print(f"wrote {out}: total={reward['total']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the host tests**

Same command as Step 2. Expected: all three PASS. If `test_matches_iteration2_mechanical_checks` shows a per-check mismatch, investigate before proceeding — a mismatch means staging or wrapping changed grading semantics, which invalidates parity. Do not weaken the assertion.

- [ ] **Step 5: Write `wsvc-0/tests/test.sh` and the verifier Dockerfile**

`wsvc-0/tests/test.sh`:
```bash
#!/bin/bash
# Runs inside the separate verifier container, which pre-bakes /tests and /grader.
set -uo pipefail
python3 /tests/run_grading.py --outputs /app/work --reward-dir /logs/verifier \
  --grader /grader/grade_checks.py --expected-head "$(cat /grader/expected_head)"
```

`verifier/Dockerfile`:
```dockerfile
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY grade_checks.py /grader/grade_checks.py
COPY expected_head /grader/expected_head
COPY tests/ /tests/
RUN chmod +x /tests/test.sh
RUN mkdir -p /app/work /logs/verifier
```

- [ ] **Step 6: Build the verifier image via the shared context assembler**

The verifier build context must always be assembled fresh from the live host files — Task 4's gate owns this logic; for now, do it by hand once:
```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
rm -rf verifier/_ctx && mkdir -p verifier/_ctx
cp ../grade_checks.py verifier/_ctx/grade_checks.py
printf '1cc113597ea87990e731f02190fc6999e42e7cd8' > verifier/_ctx/expected_head
cp -R wsvc-0/tests verifier/_ctx/tests
cp verifier/Dockerfile verifier/_ctx/Dockerfile
docker build -t wsvc-ev0-verifier:local verifier/_ctx
```

- [ ] **Step 7: Smoke the verifier image against a real graded tree**

Stage the with_skill tree to `scratch/smoke` using `_stage_arm`'s logic (small inline script reusing the test helper via `python -c` or a `scratch_stage.py`), then:
```bash
mkdir -p scratch/smoke-logs
docker run --rm -v "$PWD/scratch/smoke:/app/work" -v "$PWD/scratch/smoke-logs:/logs/verifier" \
  wsvc-ev0-verifier:local /tests/test.sh
cat scratch/smoke-logs/reward.json
```
Expected: reward.json exists; `total` matches the `"ok": true` count in iteration-2's `with_skill/mechanical_checks.json` (10). Note: the staged smoke tree contains `ticketd` at the pinned HEAD, so the sentinel passes; if it fails here, the sentinel logic (not the transfer) is wrong — fix before proceeding.

- [ ] **Step 8: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/wsvc-0/tests \
        rebuild-kit-workspace/harbor-spike/verifier/Dockerfile \
        rebuild-kit-workspace/harbor-spike/tests_host/test_run_grading.py
git commit -m "feat(harbor-spike): grading wrapper with artifact sentinel and iteration-2 regression"
```

---

### Task 3: Arm agents with sanitized policy hook

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/harbor_spike/__init__.py` (empty)
- Create: `rebuild-kit-workspace/harbor-spike/harbor_spike/wsvc_policy.py`
- Create: `rebuild-kit-workspace/harbor-spike/harbor_spike/agents.py`
- Test: `rebuild-kit-workspace/harbor-spike/tests_host/test_agents.py`

**Interfaces:**
- Consumes: `harbor.agents.installed.claude_code.ClaudeCode` (verified 0.20.0): `async setup(self, environment)`, `render_instruction(self, instruction) -> str` (called at run time via `@with_prompt_template`, dynamic dispatch — the override reaches the CLI prompt), env methods `upload_file(source_path=..., target_path=...)`, `upload_dir(source_dir=..., target_dir=...)`, `exec(command=..., user=...)`. `CLAUDE_CONFIG_DIR` is `/logs/agent/sessions`; `run()` only `mkdir -p`s inside it, so a settings.json written at setup survives. `harbor_spike/_generated/wsvc_policy.dat` from Task 1.
- Produces: import paths `harbor_spike.agents:RkBaseline` / `harbor_spike.agents:RkWithSkill` and agent names `rk-baseline` / `rk-with-skill` (job yamls set both); skill at `/opt/wsvc-kit` (verified post-upload); sanitized hook at `/installed-agent/wsvc_policy.py` + `/installed-agent/wsvc_policy.dat`; audit log `/logs/agent/wsvc_audit.jsonl` (bind-mounted → lands in each trial's `agent/` dir on the host).

- [ ] **Step 1: Write `harbor_spike/wsvc_policy.py`** (committed — must itself be free of naming strings)

```python
#!/usr/bin/env python3
"""Execution policy auditor for containerized runs.

Reads one tool-call record from stdin (PreToolUse hook protocol), appends an
audit line, and in strict mode denies calls matching the encoded pattern set.
Patterns live base64-encoded in the adjacent .dat file and are decoded only in
memory. Env: WSVC_MODE=strict|monitor (default monitor), WSVC_AUDIT_LOG=path.
"""
import base64
import json
import os
import re
import sys
from pathlib import Path

def load_patterns():
    dat = Path(__file__).with_suffix(".dat")
    if not dat.exists():
        return []
    return [re.compile(base64.b64decode(line).decode(), re.IGNORECASE)
            for line in dat.read_text().splitlines() if line.strip()]

def main() -> int:
    try:
        call = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        return 0
    mode = os.environ.get("WSVC_MODE", "monitor")
    log_path = os.environ.get("WSVC_AUDIT_LOG")
    text = json.dumps(call.get("tool_input", {}))[:4000]
    hit = any(p.search(text) for p in load_patterns())
    blocked = hit and mode == "strict"
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps({"tool": call.get("tool_name"),
                                "input": text[:300],
                                "probe_hits": hit,
                                "blocked": blocked}) + "\n")
    if blocked:
        print("This call is blocked by the execution policy for this run.",
              file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
```
**Cross-check the deny convention** (exit 2 + stderr) against `evals/isolation/guard_hook.py`, which is known-working with the same Claude Code hook protocol; match whatever it does. Note the audit line records `probe_hits` as a boolean, never the pattern text — the log lives in the agent-readable `/logs/agent` mount.

- [ ] **Step 2: Write the failing tests**

`tests_host/test_agents.py`:
```python
import asyncio
import base64
import json
from pathlib import Path

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.agents.installed.claude_code import ClaudeCode

from harbor_spike.agents import RkBaseline, RkWithSkill, SKILL_CONTAINER_DIR

SPIKE = Path(__file__).resolve().parents[1]

class FakeEnv:
    def __init__(self):
        self.execs, self.uploaded_files, self.uploaded_dirs = [], [], []
    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.execs.append(command)
        class R: return_code = 0; stdout = "direct"; stderr = ""
        return R()
    async def upload_file(self, source_path, target_path):
        self.uploaded_files.append((str(source_path), target_path))
    async def upload_dir(self, source_dir, target_dir):
        self.uploaded_dirs.append((str(source_dir), target_dir))

def make(cls, tmp_path):
    return cls(logs_dir=tmp_path / "logs", model_name="claude-sonnet-5")

def test_baseline_instruction_untouched(tmp_path):
    assert make(RkBaseline, tmp_path).render_instruction("do the thing") == "do the thing"

def test_with_skill_instruction_appends_suffix(tmp_path):
    out = make(RkWithSkill, tmp_path).render_instruction("do the thing")
    assert out.startswith("do the thing")
    assert SKILL_CONTAINER_DIR in out and "SKILL.md" in out

def test_suffix_matches_run_arm():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_arm", SPIKE.parent / "evals" / "isolation" / "run_arm.py")
    run_arm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_arm)
    from harbor_spike.agents import WITH_SKILL_SUFFIX
    assert WITH_SKILL_SUFFIX == run_arm.WITH_SKILL_SUFFIX

def test_policy_wiring_baseline_strict(tmp_path):
    env = FakeEnv()
    asyncio.run(make(RkBaseline, tmp_path).install_policy(env))
    targets = [t for _, t in env.uploaded_files]
    assert "/installed-agent/wsvc_policy.py" in targets
    assert "/installed-agent/wsvc_policy.dat" in targets
    settings_src = next(s for s, t in env.uploaded_files
                        if t == "/logs/agent/sessions/settings.json")
    cmd = json.loads(Path(settings_src).read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "WSVC_MODE=strict" in cmd
    assert "WSVC_AUDIT_LOG=/logs/agent/wsvc_audit.jsonl" in cmd

def test_policy_wiring_with_skill_monitor_and_skill_upload(tmp_path):
    env = FakeEnv()
    agent = make(RkWithSkill, tmp_path)
    asyncio.run(agent.install_policy(env))
    asyncio.run(agent.upload_skill(env))
    settings_src = next(s for s, t in env.uploaded_files
                        if t == "/logs/agent/sessions/settings.json")
    assert "WSVC_MODE=monitor" in Path(settings_src).read_text()
    assert env.uploaded_dirs and env.uploaded_dirs[0][1] == SKILL_CONTAINER_DIR

def test_container_payloads_sanitized(tmp_path):
    """Nothing uploaded into an agent container may name the skill or the eval."""
    env = FakeEnv()
    agent = make(RkBaseline, tmp_path)
    asyncio.run(agent.install_policy(env))
    banned = ["rebuild", "skill", "render_guide", "scaffold", "guard", "eval"]
    for src, tgt in env.uploaded_files:
        content = Path(src).read_text(errors="replace").lower()
        for word in banned:
            assert word not in content, f"{tgt} contains banned string {word!r}"

def test_setup_and_render_signatures_match_base():
    import inspect
    assert inspect.signature(RkBaseline.setup) == inspect.signature(BaseInstalledAgent.setup)
    assert inspect.signature(RkWithSkill.render_instruction) == \
        inspect.signature(ClaudeCode.render_instruction)

def test_agent_names_differ():
    assert RkBaseline.name() != RkWithSkill.name()
```

- [ ] **Step 3: Run to verify failure**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
PYTHONPATH=. .venv/bin/python -m pytest tests_host/test_agents.py -v
```
Expected: FAIL with import error (`harbor_spike.agents` missing).

- [ ] **Step 4: Write `harbor_spike/agents.py`**

```python
"""The two eval arms as Harbor agents.

RkBaseline is the stock ClaudeCode adapter plus the sanitized policy hook
(strict mode). RkWithSkill additionally uploads the skill into the container at
a neutral path — verifying it landed where the prompt promises — and appends
the same suffix run_arm.py uses. Session persistence stays at the adapter
default: Harbor consumes the session JSONL for trajectory/cost accounting, and
fresh per-trial containers provide the isolation the seatbelt flag provided.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import override

from harbor.agents.installed.claude_code import ClaudeCode

SPIKE = Path(__file__).resolve().parents[1]
WORKSPACE = SPIKE.parent
REPO = WORKSPACE.parent
SKILL_SOURCE_DIR = REPO / "rebuild-kit"
POLICY_SOURCE = SPIKE / "harbor_spike" / "wsvc_policy.py"
POLICY_DAT = SPIKE / "harbor_spike" / "_generated" / "wsvc_policy.dat"

SKILL_CONTAINER_DIR = "/opt/wsvc-kit"
POLICY_TARGET = "/installed-agent/wsvc_policy.py"
POLICY_DAT_TARGET = "/installed-agent/wsvc_policy.dat"
SETTINGS_TARGET = "/logs/agent/sessions/settings.json"
AUDIT_LOG = "/logs/agent/wsvc_audit.jsonl"

# Keep identical to run_arm.WITH_SKILL_SUFFIX (enforced by tests_host).
WITH_SKILL_SUFFIX = (
    "\n\nA skill that may help with this task is installed at {skill_dir}. "
    "Read {skill_dir}/SKILL.md first and follow it."
)


class RkBaseline(ClaudeCode):
    POLICY_MODE = "strict"

    @staticmethod
    @override
    def name() -> str:
        return "rk-baseline"

    def _settings_payload(self) -> dict:
        command = (
            f"WSVC_MODE={self.POLICY_MODE} WSVC_AUDIT_LOG={AUDIT_LOG} "
            f"python3 {POLICY_TARGET}"
        )
        return {"hooks": {"PreToolUse": [
            {"matcher": "*", "hooks": [{"type": "command", "command": command}]}
        ]}}

    async def install_policy(self, environment) -> None:
        if not POLICY_DAT.exists():
            raise RuntimeError("wsvc_policy.dat missing — run prepare_task.py first")
        await environment.exec(command="mkdir -p /logs/agent/sessions /installed-agent",
                               user="root")
        await environment.upload_file(source_path=POLICY_SOURCE, target_path=POLICY_TARGET)
        await environment.upload_file(source_path=POLICY_DAT, target_path=POLICY_DAT_TARGET)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(self._settings_payload(), f, indent=1)
            settings_src = f.name
        await environment.upload_file(source_path=settings_src, target_path=SETTINGS_TARGET)

    @override
    async def setup(self, environment) -> None:
        await super().setup(environment)
        await self.install_policy(environment)


class RkWithSkill(RkBaseline):
    POLICY_MODE = "monitor"

    @staticmethod
    @override
    def name() -> str:
        return "rk-with-skill"

    @override
    def render_instruction(self, instruction: str) -> str:
        rendered = super().render_instruction(instruction)
        return rendered + WITH_SKILL_SUFFIX.format(skill_dir=SKILL_CONTAINER_DIR)

    async def upload_skill(self, environment) -> None:
        await environment.exec(command=f"mkdir -p {SKILL_CONTAINER_DIR}", user="root")
        await environment.upload_dir(source_dir=SKILL_SOURCE_DIR,
                                     target_dir=SKILL_CONTAINER_DIR)
        # upload_dir semantics (copy-into vs copy-as) are backend-defined; verify
        # and repair so the prompt's promised path is always real, or die loudly.
        nested = f"{SKILL_CONTAINER_DIR}/{SKILL_SOURCE_DIR.name}"
        probe = await environment.exec(
            command=(f"if [ -f {SKILL_CONTAINER_DIR}/SKILL.md ]; then echo direct; "
                     f"elif [ -f {nested}/SKILL.md ]; then echo nested; "
                     f"else echo missing; fi"))
        layout = (probe.stdout or "").strip()
        if layout == "nested":
            await environment.exec(
                command=f"sh -c 'mv {nested}/* {nested}/.[!.]* {SKILL_CONTAINER_DIR}/ "
                        f"2>/dev/null; rmdir {nested}'",
                user="root")
        elif layout != "direct":
            raise RuntimeError(f"skill upload landed nowhere expected: {layout!r}")

    @override
    async def setup(self, environment) -> None:
        await super().setup(environment)
        await self.upload_skill(environment)
```

- [ ] **Step 5: Run the tests**

Same command as Step 3. Expected: all PASS. `test_container_payloads_sanitized` is the finding-1 regression: if it fails, the sanitization is broken — never fix it by removing the assertion. If a signature test fails, read `.venv/lib/python3.12/site-packages/harbor/agents/installed/base.py` and match exactly.

- [ ] **Step 6: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/harbor_spike rebuild-kit-workspace/harbor-spike/tests_host/test_agents.py
git commit -m "feat(harbor-spike): arm agents with sanitized policy hook and skill-upload verification"
```

---

### Task 4: Isolation gate — build-then-probe

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/verify_container_isolation.py`
- Test: `rebuild-kit-workspace/harbor-spike/tests_host/test_verify_isolation.py`

**Interfaces:**
- Consumes: `wsvc-0/environment/` and `verifier/` build contexts; `wsvc-0/task.toml`; job yaml paths via `--job-config` (repeatable).
- Produces: exit 0 = safe to run, having **rebuilt both images from current contexts** and written their IDs to `scratch/image_ids.json`; nonzero with a printed reason otherwise. Tasks 5/7/8 call it as the gate immediately before `harbor run`.

- [ ] **Step 1: Write the failing test**

`tests_host/test_verify_isolation.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parents[1]
SCRIPT = SPIKE / "verify_container_isolation.py"

def run_verify(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=SPIKE)

def test_passes_on_clean_contexts_and_records_ids():
    r = run_verify("--job-config", "job-shakedown.yaml")
    assert r.returncode == 0, r.stdout + r.stderr
    ids = json.loads((SPIKE / "scratch" / "image_ids.json").read_text())
    assert ids["agent"].startswith("sha256:") and ids["verifier"].startswith("sha256:")

def test_fails_on_planted_skill_marker(tmp_path):
    plant = SPIKE / "wsvc-0" / "environment" / "context" / "planted_SKILL.md"
    plant.write_text("leaked\n")
    try:
        r = run_verify()
        assert r.returncode != 0
        assert "SKILL" in r.stdout + r.stderr
    finally:
        plant.unlink()
```
(The plant goes into the *build context*, exercising the build-then-probe path — the review found probing a pre-built tag certifies stale bytes.)

- [ ] **Step 2: Run to verify failure**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests_host/test_verify_isolation.py -v
```
Expected: FAIL (script missing). Note: these tests require Task 1's context staged (`prepare_task.py` run) and Docker up.

- [ ] **Step 3: Write `verify_container_isolation.py`**

```python
#!/usr/bin/env python3
"""Pre-flight isolation gate (container port of verify_isolation.py's spirit).

Key property: the gate REBUILDS both images from the current build contexts and
probes the images it just built, then records their IDs — so what it certifies
is byte-identical to what Harbor trials run. Probing a previously built tag
certifies nothing.

Checks:
  1. rebuild agent + verifier images; write IDs to scratch/image_ids.json
  2. task.toml: verifier separate mode
  3. job yaml(s): no host mounts at the layer Harbor actually accepts them
  4. agent image: no skill/assertion/prior-iteration marker files (globbed),
     no 'rebuild-kit' string in the writable roots
  5. verifier image: holds the grader by design, but never the skill or
     prior-iteration outputs

The live checks (audit log firing, skill landing, hostname hygiene) happen in
the Task 5 shakedown; report.py re-checks audit presence per scored trial.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
WORKSPACE = SPIKE.parent

AGENT_MARKERS = ["SKILL.md", "evals.json", "render_guide*", "scaffold*",
                 "*rebuild-kit*", "grade_checks*", "mechanical_checks*",
                 "grading.json", "benchmark.json"]
VERIFIER_MARKERS = ["SKILL.md", "evals.json", "render_guide*", "scaffold*",
                    "*rebuild-kit*", "mechanical_checks*", "grading.json",
                    "benchmark.json"]

def sh(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

def fail(msg: str):
    print(f"ISOLATION FAIL: {msg}")
    sys.exit(1)

def build_images() -> dict[str, str]:
    code, out = sh(["docker", "build", "-t", "wsvc-ev0:local",
                    str(SPIKE / "wsvc-0" / "environment")])
    if code != 0:
        fail(f"agent image build failed:\n{out[-2000:]}")
    ctx = SPIKE / "verifier" / "_ctx"
    if ctx.exists():
        shutil.rmtree(ctx)
    ctx.mkdir(parents=True)
    shutil.copy2(WORKSPACE / "grade_checks.py", ctx / "grade_checks.py")
    (ctx / "expected_head").write_text("1cc113597ea87990e731f02190fc6999e42e7cd8")
    shutil.copytree(SPIKE / "wsvc-0" / "tests", ctx / "tests")
    shutil.copy2(SPIKE / "verifier" / "Dockerfile", ctx / "Dockerfile")
    code, out = sh(["docker", "build", "-t", "wsvc-ev0-verifier:local", str(ctx)])
    if code != 0:
        fail(f"verifier image build failed:\n{out[-2000:]}")
    ids = {}
    for key, tag in (("agent", "wsvc-ev0:local"), ("verifier", "wsvc-ev0-verifier:local")):
        code, out = sh(["docker", "image", "inspect", "--format", "{{.Id}}", tag])
        if code != 0:
            fail(f"cannot inspect {tag}")
        ids[key] = out.strip()
    (SPIKE / "scratch").mkdir(exist_ok=True)
    (SPIKE / "scratch" / "image_ids.json").write_text(json.dumps(ids, indent=1))
    return ids

def probe_image(image: str, markers: list[str], grep_string: str | None,
                grep_targets: str):
    name_expr = " -o ".join(f'-name "{m}"' for m in markers)
    code, out = sh(["docker", "run", "--rm", image, "sh", "-c",
                    f"find / \\( {name_expr} \\) -not -path '/proc/*' 2>/dev/null; true"])
    if code != 0:
        fail(f"cannot probe image {image}: {out}")
    hits = [l for l in out.splitlines() if l.strip()]
    if hits:
        fail(f"marker files present in {image}: {hits[:5]}")
    if grep_string:
        code, out = sh(["docker", "run", "--rm", image, "sh", "-c",
                        f"grep -rl '{grep_string}' {grep_targets} 2>/dev/null; true"])
        hits = [l for l in out.splitlines() if l.strip()]
        if hits:
            fail(f"'{grep_string}' string present in {image}: {hits[:5]}")

def check_task_toml():
    cfg = tomllib.loads((SPIKE / "wsvc-0" / "task.toml").read_text())
    if cfg.get("verifier", {}).get("environment_mode") != "separate":
        fail("verifier is not in separate mode — grading code would enter the agent container")

def check_job_configs(paths: list[str]):
    # Host bind-mounts live at the job/trial level in 0.20.0
    # (harbor/models/trial/config.py: EnvironmentConfig.mounts), not in task.toml.
    import yaml  # harbor dependency, present in the venv
    for p in paths:
        data = yaml.safe_load(Path(p).read_text()) or {}
        env = data.get("environment") or {}
        if env.get("mounts"):
            fail(f"{p} declares host mounts — forbidden for isolation runs")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-config", action="append", default=[])
    args = ap.parse_args()

    check_task_toml()
    check_job_configs(args.job_config)
    ids = build_images()
    probe_image("wsvc-ev0:local", AGENT_MARKERS, "rebuild-kit",
                "/opt /app /root /home /installed-agent /tests /grader")
    # Verifier image: /grader and /tests legitimately reference the project, so
    # the string grep is scoped to everything else.
    probe_image("wsvc-ev0-verifier:local", VERIFIER_MARKERS, "rebuild-kit",
                "/opt /app /root /home /installed-agent")
    print(f"isolation checks passed; images {ids['agent'][:19]} / {ids['verifier'][:19]}")

if __name__ == "__main__":
    main()
```
Note the deltas from v1, each a review finding: the gate builds what it probes (f3), marker names are globs (f13), the "rebuild-kit" grep never scans the verifier's `/grader`/`/tests` (f6 — the grader's own docstring contains the string), the verifier is additionally probed for `evals.json` and both images for prior-iteration markers (f18), and the mount check moved to the job-yaml layer where Harbor actually accepts mounts (f14).

- [ ] **Step 4: Run the tests**

Same command as Step 2 (after `prepare_task.py` and with `job-shakedown.yaml` present — if executing tasks in order, create a stub of that yaml now from Task 5 Step 1). Expected: PASS both.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/verify_container_isolation.py \
        rebuild-kit-workspace/harbor-spike/tests_host/test_verify_isolation.py
git commit -m "feat(harbor-spike): build-then-probe isolation gate"
```

---

### Task 5: Shakedown — one live trial per arm (empirical unknowns)

Resolves the mechanics no source documents: artifact round-trip into the separate verifier, settings/hook survival, skill-upload layout, container-identity hygiene. Budget: 2 paid trials (authorized by this plan). Expect iteration.

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/job-shakedown.yaml`
- Create (running notes): `rebuild-kit-workspace/harbor-spike/SPIKE-NOTES.md`
- Modify (if needed): `wsvc-0/task.toml`, `harbor_spike/agents.py` — only to make mechanics work, never to change grading or framing semantics.

**Interfaces:**
- Consumes: everything from Tasks 1–4; `ANTHROPIC_API_KEY` in the host env.
- Produces: one passing trial per arm in `$SPIKE/jobs/shakedown/`; recorded answers in SPIKE-NOTES.md.

- [ ] **Step 1: Write `job-shakedown.yaml`** (both arms — the review found v1 shook down baseline only, leaving RkWithSkill's first execution inside the paid batch)

```yaml
job_name: shakedown
jobs_dir: jobs
n_attempts: 1
n_concurrent_trials: 2
tasks:
  - path: ./wsvc-0
agents:
  - name: rk-baseline
    import_path: harbor_spike.agents:RkBaseline
    model_name: claude-sonnet-5
  - name: rk-with-skill
    import_path: harbor_spike.agents:RkWithSkill
    model_name: claude-sonnet-5
```

- [ ] **Step 2: Gate, launch, and watch container identity**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
.venv/bin/python prepare_task.py
.venv/bin/python verify_container_isolation.py --job-config job-shakedown.yaml || exit 1
PYTHONPATH=. .venv/bin/harbor run -c job-shakedown.yaml -y &
sleep 90 && docker ps --format '{{.Names}}' | tee scratch/container-names.txt
CID=$(docker ps -q | head -1); docker exec "$CID" sh -c 'hostname; env' | grep -iE 'skill|rebuild|eval-' ; echo "identity-grep exit: $?"
wait
```
Expected: container names derive from `wsvc-0` (no `eval`/`skill`/`rebuild` substrings — finding 12's check), and the identity grep exits 1 (no hits). If names leak the eval, find where Harbor derives them (trial name = task dir name) and rename accordingly before proceeding.

- [ ] **Step 3: Verify both trial records**

For EACH of the two trial dirs under `jobs/shakedown/`:
1. `result.json` exists, `exception_info` null; `verifier_result.rewards` has the Task 2 keys (per-check + `total` + `unscoreable`).
2. `verifier/test-stdout.txt` shows grade_checks output with real evidence for `layout-and-pin` and `legacy-protected` — proves the artifact round-trip carried `/app/work` including `.git` trees (and that the sentinel passed).
3. `agent/wsvc_audit.jsonl` non-empty (live hook check — the silent-hook failure mode from RUN-PROTOCOL.md).
4. `agent/sessions/settings.json` present on the host (bind-mounted) and still containing the hook wiring.
5. With-skill trial only: the transcript (`agent/claude-code.txt`) shows the suffix in the prompt and the agent reading `/opt/wsvc-kit/SKILL.md`; audit log has `probe_hits` entries without `blocked` (monitor mode).
6. Baseline trial only: transcript contains no mention of a skill; if `probe_hits` occur, `blocked: true` accompanies them.
Also note in SPIKE-NOTES.md whether the artifact copy preserved the legacy tree's read-only bits (`legacy-protected` evidence line) — if not, that check's semantics changed; record it, do not patch grade_checks.

- [ ] **Step 4: Debug loop for the known-risky seams (as needed)**

Consult the installed source (`.venv/lib/python3.12/site-packages/harbor/`), not docs:
- **Rewards missing with sentinel stderr** → the artifact transfer really is broken: inspect `<trial>/artifacts/manifest.json` and `harbor/trial/artifact_handler.py`; adjust the `artifacts` declaration.
- **Audit log empty** → check whether the CLI honors `CLAUDE_CONFIG_DIR/settings.json`; if not, fall back to writing `/root/.claude/settings.json` (agent user's home) — update `SETTINGS_TARGET`, the tests, and SPIKE-NOTES.
- **Settings wiped** → move `install_policy` after the adapter's config-dir setup by overriding `run()` to call `await self.install_policy(environment)` before `await super().run(...)`; keep the write idempotent.
- **Skill layout `missing`** → the `upload_skill` probe raised; read the exec/upload backend for the env type and fix the repair branch.
Record every deviation in SPIKE-NOTES.md.

- [ ] **Step 5: Re-run until Step 2–3 checks pass for both arms, then commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/job-shakedown.yaml rebuild-kit-workspace/harbor-spike/SPIKE-NOTES.md
git commit -m "feat(harbor-spike): two-arm shakedown passing with separate-verifier grading and live policy hook"
```

---

### Task 6: Parity report generator

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/harbor_spike/report.py`
- Test: `rebuild-kit-workspace/harbor-spike/tests_host/test_report.py`

**Interfaces:**
- Consumes: one or more Harbor job dirs (trial dirs sit flat under each, verified): `<trial>/config.json` (serialized TrialConfig; agent `name` present because the job yamls set it — f10), `<trial>/verifier/reward.json`, `<trial>/result.json`, `<trial>/agent/wsvc_audit.jsonl`. Iteration-2 stored results: `iteration-2-sonnet/eval-0-full-generation/<arm>/mechanical_checks.json`.
- Produces: `python -m harbor_spike.report --job-dir jobs/parity [--job-dir jobs/<rerun>...] --expected-per-arm 10 --out SPIKE-REPORT.md`. Verdict per amended spec §6, **all references computed from stored mechanical_checks.json** (with-skill ref 10, baseline ref 3 — computed, never hardcoded): with-skill mean ≥ ws_ref − 1.0; |baseline mean − bl_ref| ≤ 1.5; gap ≥ 4.0; zero invalid trials. Trials with a missing/empty audit log are **invalid**, not scored (f4). Per-arm accounting must satisfy scored + infra + invalid == expected (f9).

- [ ] **Step 1: Write the failing test**

`tests_host/test_report.py`:
```python
import json
import pytest
from pathlib import Path

from harbor_spike.report import collect_trials, parity_verdict, references, render_markdown

def make_trial(job: Path, name: str, agent_name, import_path: str,
               rewards: dict | None, exc: str | None = None, audit_lines: int = 3):
    t = job / name
    (t / "verifier").mkdir(parents=True)
    (t / "agent").mkdir(parents=True)
    # Mirror the real shape: `name` may be null when only import_path is set.
    (t / "config.json").write_text(json.dumps(
        {"agent": {"name": agent_name, "import_path": import_path}}))
    (t / "result.json").write_text(json.dumps(
        {"exception_info": ({"exception_type": exc} if exc else None)}))
    if rewards is not None:
        (t / "verifier" / "reward.json").write_text(json.dumps(rewards))
    (t / "agent" / "wsvc_audit.jsonl").write_text(
        "\n".join('{"tool":"Bash","probe_hits":false,"blocked":false}'
                  for _ in range(audit_lines)))

def test_collect_verdict_and_accounting(tmp_path):
    job = tmp_path / "job"; rerun = tmp_path / "rerun"
    make_trial(job, "t1", "rk-with-skill", "harbor_spike.agents:RkWithSkill",
               {"a": 1.0, "total": 10.0, "unscoreable": 0.0})
    make_trial(job, "t2", None, "harbor_spike.agents:RkBaseline",   # null name: normalized
               {"a": 0.0, "total": 3.0, "unscoreable": 2.0})
    make_trial(job, "t3", "rk-baseline", "harbor_spike.agents:RkBaseline",
               None, exc="ApiError")                                 # infra: unscored
    make_trial(job, "t4", "rk-baseline", "harbor_spike.agents:RkBaseline",
               {"a": 0.0, "total": 3.0, "unscoreable": 2.0}, audit_lines=0)  # invalid
    make_trial(rerun, "t5", "rk-baseline", "harbor_spike.agents:RkBaseline",
               {"a": 1.0, "total": 4.0, "unscoreable": 1.0})         # rerun dir merged
    arms = collect_trials([job, rerun])
    bl = arms["rk-baseline"]
    assert len(bl.scored) == 2 and len(bl.infra_failures) == 1 and len(bl.invalid) == 1
    refs = references()
    assert refs == {"rk-with-skill": 10.0, "rk-baseline": 3.0}  # computed from stored files
    verdict = parity_verdict(arms, refs)
    assert verdict.with_skill_mean == 10.0
    assert not verdict.passed  # invalid trial present blocks PASS
    md = render_markdown(arms, verdict, expected_per_arm=2)
    assert "invalid" in md.lower() and "rk-baseline" in md

def test_verdict_raises_on_missing_arm(tmp_path):
    job = tmp_path / "job"
    make_trial(job, "t1", "rk-with-skill", "harbor_spike.agents:RkWithSkill",
               {"total": 10.0, "unscoreable": 0.0})
    with pytest.raises(ValueError):
        parity_verdict(collect_trials([job]), references())
```

- [ ] **Step 2: Run to verify failure**

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests_host/test_report.py -v
```
Expected: FAIL (report module missing).

- [ ] **Step 3: Write `harbor_spike/report.py`**

```python
"""Fold Harbor trial outputs (across one or more job dirs, including reruns)
into the parity report. All iteration-2 references are computed from the stored
mechanical_checks.json files — never hardcoded — because the spike measures the
mechanical scale only (the analyst-graded 10/10 vs 4/10 is a different scale,
printed for context)."""
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

SPIKE = Path(__file__).resolve().parents[1]
IT2_EVAL0 = SPIKE.parent / "iteration-2-sonnet" / "eval-0-full-generation"
ARM_FROM_CLASS = {"RkBaseline": "rk-baseline", "RkWithSkill": "rk-with-skill"}
GRADED_CONTEXT = "analyst-graded (grading.json) context: with-skill 10/10, baseline 4/10 — different scale, not the parity basis"

@dataclass
class ArmResults:
    name: str
    scored: list[dict] = field(default_factory=list)
    infra_failures: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)      # scored-looking but audit log absent/empty

    def mean_total(self) -> float:
        return statistics.mean(r["total"] for r in self.scored) if self.scored else 0.0

    def check_pass_rate(self) -> dict[str, float]:
        keys = [k for k in (self.scored[0] if self.scored else {})
                if k not in ("total", "unscoreable", "grader_error")]
        return {k: statistics.mean(r.get(k, 0.0) for r in self.scored) for k in keys}

@dataclass
class Verdict:
    with_skill_mean: float
    baseline_mean: float
    refs: dict[str, float]
    gap: float
    invalid_count: int
    passed: bool

def _arm_name(cfg: dict) -> str:
    agent = cfg.get("agent") or {}
    if agent.get("name"):
        return agent["name"]
    cls = str(agent.get("import_path", "")).split(":")[-1]
    return ARM_FROM_CLASS.get(cls, cls or "unknown")

def collect_trials(job_dirs: list[Path]) -> dict[str, ArmResults]:
    arms: dict[str, ArmResults] = {}
    for job_dir in job_dirs:
        for trial in sorted(p for p in Path(job_dir).iterdir()
                            if (p / "config.json").exists()):
            cfg = json.loads((trial / "config.json").read_text())
            arm = arms.setdefault(_arm_name(cfg), ArmResults(_arm_name(cfg)))
            result_path = trial / "result.json"
            result = json.loads(result_path.read_text()) if result_path.exists() else {}
            reward_path = trial / "verifier" / "reward.json"
            audit = trial / "agent" / "wsvc_audit.jsonl"
            if result.get("exception_info") or not reward_path.exists():
                arm.infra_failures.append(trial.name)
            elif not audit.exists() or not audit.read_text().strip():
                arm.invalid.append(trial.name)      # policy hook never fired: not a valid sample
            else:
                arm.scored.append(json.loads(reward_path.read_text()))
    return arms

def references() -> dict[str, float]:
    refs = {}
    for arm_key, stored_dir in (("rk-with-skill", "with_skill"),
                                ("rk-baseline", "without_skill")):
        stored = json.loads((IT2_EVAL0 / stored_dir / "mechanical_checks.json").read_text())
        refs[arm_key] = float(sum(1 for r in stored.values() if r.get("ok") is True))
    return refs

def parity_verdict(arms: dict[str, ArmResults], refs: dict[str, float]) -> Verdict:
    for key in ("rk-with-skill", "rk-baseline"):
        if key not in arms:
            raise ValueError(f"arm {key!r} missing from results — check agent names in job yaml")
    ws, bl = arms["rk-with-skill"], arms["rk-baseline"]
    invalid = len(ws.invalid) + len(bl.invalid)
    gap = ws.mean_total() - bl.mean_total()
    passed = (ws.mean_total() >= refs["rk-with-skill"] - 1.0
              and abs(bl.mean_total() - refs["rk-baseline"]) <= 1.5
              and gap >= 4.0
              and invalid == 0)
    return Verdict(ws.mean_total(), bl.mean_total(), refs, gap, invalid, passed)

def render_markdown(arms: dict[str, ArmResults], verdict: Verdict,
                    expected_per_arm: int | None = None) -> str:
    lines = ["# Harbor spike — eval-0 parity report (mechanical scale)", ""]
    lines.append(f"**Parity verdict: {'PASS' if verdict.passed else 'FAIL'}** — "
                 f"with-skill mean {verdict.with_skill_mean:.1f} (ref "
                 f"{verdict.refs['rk-with-skill']:.0f}), baseline mean "
                 f"{verdict.baseline_mean:.1f} (ref {verdict.refs['rk-baseline']:.0f}), "
                 f"gap {verdict.gap:.1f}, invalid trials {verdict.invalid_count}.")
    lines.append(f"\n_{GRADED_CONTEXT}_")
    for arm in arms.values():
        counts = (f"scored {len(arm.scored)}, infra (rerun, unscored) "
                  f"{len(arm.infra_failures)} {arm.infra_failures}, "
                  f"invalid (no audit log) {len(arm.invalid)} {arm.invalid}")
        lines += ["", f"## {arm.name}", f"- {counts}"]
        if expected_per_arm is not None:
            total = len(arm.scored) + len(arm.infra_failures) + len(arm.invalid)
            lines.append(f"- accounting: {total}/{expected_per_arm} trials "
                         f"{'OK' if total == expected_per_arm else '**MISMATCH**'}")
        lines += [f"- mean total: {arm.mean_total():.2f}", "",
                  "| check | pass rate |", "|---|---|"]
        lines += [f"| {k} | {v:.0%} |" for k, v in sorted(arm.check_pass_rate().items())]
    return "\n".join(lines) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", action="append", required=True)
    ap.add_argument("--expected-per-arm", type=int, default=None)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()
    arms = collect_trials([Path(d) for d in args.job_dir])
    verdict = parity_verdict(arms, references())
    md = render_markdown(arms, verdict, expected_per_arm=args.expected_per_arm)
    if args.out == "-":
        print(md)
    else:
        Path(args.out).write_text(md)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests, then reconcile with reality**

Same command as Step 2. Expected: PASS. Then open a real `config.json` from the Task 5 shakedown job and confirm the agent name/import-path field layout matches `_arm_name`'s expectations; if the serialized `TrialConfig` nests differently, fix `_arm_name` AND the synthetic fixtures to the real shape.

- [ ] **Step 5: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/harbor_spike/report.py rebuild-kit-workspace/harbor-spike/tests_host/test_report.py
git commit -m "feat(harbor-spike): parity report with computed references and per-trial validity"
```

---

### Task 7: Parity run (20 paid trials) — USER GATE

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/job-parity.yaml`

**Interfaces:**
- Consumes: everything prior; `ANTHROPIC_API_KEY`.
- Produces: `jobs/parity/` (+ possible rerun job dirs) totalling 10 scored trials per arm; `SPIKE-REPORT.md` parity section; `jobs/parity/image_ids.json`.

- [ ] **Step 1: Confirm retry semantics from source, then write `job-parity.yaml`**

Read `.venv/lib/python3.12/site-packages/harbor/models/job/config.py` (`RetryConfig`) and the agent error taxonomy in `harbor/agents/installed/base.py`. Set `include_exceptions` to infra-only errors (API/network), so Harbor never auto-retries an agent that ran and produced a bad workspace — that distinction is the spec's rerun convention. Use the exact class names found in source; the yaml below shows the intent:

```yaml
job_name: parity
jobs_dir: jobs
n_attempts: 10
n_concurrent_trials: 4
retry:
  max_retries: 2
  include_exceptions: ["ApiError", "ApiRateLimitError", "ApiInternalServerError",
                       "ApiOverloadedError", "NetworkConnectionError"]
tasks:
  - path: ./wsvc-0
agents:
  - name: rk-baseline
    import_path: harbor_spike.agents:RkBaseline
    model_name: claude-sonnet-5
  - name: rk-with-skill
    import_path: harbor_spike.agents:RkWithSkill
    model_name: claude-sonnet-5
```
Verify with `PYTHONPATH=. .venv/bin/harbor run -c job-parity.yaml --print-config` that this resolves to 1 task × 2 agents × 10 attempts = 20 trials before presenting the gate.

- [ ] **Step 2: STOP — user confirmation gate**

Present to the user: 20 trials (10/arm), model `claude-sonnet-5`, **worst-case 60 agent executions** if every trial retried twice on infra errors (typical: 20–24), token cost by reference to iteration-2's per-run cost, sandbox compute local/free. **Do not launch without an explicit yes.**

- [ ] **Step 3: Gate (rebuilds images), launch, record image IDs**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit/rebuild-kit-workspace/harbor-spike
.venv/bin/python prepare_task.py
.venv/bin/python verify_container_isolation.py --job-config job-parity.yaml || exit 1
PYTHONPATH=. .venv/bin/harbor run -c job-parity.yaml -y 2>&1 | tee jobs/parity-run.log
cp scratch/image_ids.json jobs/parity/image_ids.json
```
**Do not rebuild either image while the job is running** — mid-job rebuilds make trials incomparable; the recorded IDs are the audit trail. Expect a few hours wall-clock at `-n 4`.

- [ ] **Step 4: Triage and rerun**

For each trial with `exception_info` set or reward.json missing: infra exception → rerun via a small `n_attempts=1` job per missing slot with the same agent entry (each rerun gets its own job dir — record the dir names); agent-produced-bad-workspace → scored as-is, never rerun. Also list any trial `report.py` will classify invalid (empty `agent/wsvc_audit.jsonl`) — an invalid trial means hook wiring broke mid-batch: stop, diagnose against the recorded image IDs, and rerun those slots too. Record the full split in SPIKE-NOTES.md.

- [ ] **Step 5: Generate the parity report over ALL job dirs**

```bash
PYTHONPATH=. .venv/bin/python -m harbor_spike.report \
  --job-dir jobs/parity --job-dir jobs/<each-rerun-dir> \
  --expected-per-arm 10 --out SPIKE-REPORT.md
```
Read it. The accounting line must show 10/10 per arm; a MISMATCH means dropped trials (the exact "rerun degraded to dropped" failure the review flagged). Sanity-check per-check pass rates against iteration-2's per-check `ok` values — a check that flips universally (e.g. `legacy-protected` if the artifact copy loses read-only bits) is a mechanics artifact, not a skill signal; annotate it in the report.

- [ ] **Step 6: Commit**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/job-parity.yaml rebuild-kit-workspace/harbor-spike/SPIKE-REPORT.md rebuild-kit-workspace/harbor-spike/SPIKE-NOTES.md
git commit -m "test(harbor-spike): eval-0 parity run results"
```
If trial outputs should be archived like iterations are, run `evals/git_bundles.py pack` on a copied `jobs/parity` dir first — decide with the user.

---

### Task 8 (POST-PARITY, OPTIONAL): Network allowlist hardening — USER GATE

Runs **only after Task 7**, so the parity measurement's environment stays fixed (review finding 8: v1 ran this between shakedown and parity). Budget: up to 4 cheap trials, behind its own user gate. Timebox: 3 attempts; on failure, revert and record.

**Files:**
- Create: `rebuild-kit-workspace/harbor-spike/wsvc-net-probe/` (tiny canary task: `instruction.md` = "Run exactly this and then stop: `curl -sS --max-time 10 https://github.com -o /dev/null; echo exit=$?`", `task.toml` mirroring wsvc-0's with the allowlist keys, `environment/Dockerfile` = `FROM wsvc-ev0:local`, `tests/test.sh` writing `{"reward": 1.0}` unconditionally)
- Modify: `wsvc-0/task.toml` (only if the experiment succeeds and the user wants it kept)

- [ ] **Step 1: Pre-check egress enforcement support on this host**

Harbor enables egress control only when `sys.platform == "linux"` or the Docker kernel supports it (`environments/docker/docker.py:188-195`). Read that check and run its equivalent against Docker Desktop's VM. If unsupported: record "allowlist not enforceable on this host" in SPIKE-NOTES.md and stop this task — do not fake it.

- [ ] **Step 2: Put the hosts on the layer that covers install (review finding 7)**

`AgentConfig.extra_allowed_hosts` applies only during `agent.run()`; the Claude Code install curls `downloads.claude.ai` during `setup()`, which runs under the `[environment]` baseline. So the hosts go in the task.toml baseline:
```toml
[environment]
network_mode = "allowlist"
allowed_hosts = ["api.anthropic.com", "downloads.claude.ai", "statsig.anthropic.com"]
```
(In the canary task's task.toml. Confirm the exact key name from `BaselineNetworkPolicyConfig` in `harbor/models/task/config.py:36-41` before writing.)

- [ ] **Step 3: USER GATE, then run the canary and one baseline trial**

Present cost (up to 4 cheap trials) and get a yes. Then: run the canary task with RkBaseline — success = trial completes AND the transcript shows `exit=` nonzero (the deliberate negative probe: github.com must be unreachable). Then one full wsvc-0 baseline trial — success = the four Task 5 checks pass under allowlist.

- [ ] **Step 4: Decide and record**

- Works: record "enforcement-grade network isolation achieved" in SPIKE-NOTES.md with the canary evidence; offer the user the option to adopt the allowlist keys into `wsvc-0/task.toml` for future runs (a config change to the measured environment — their call, noted as a delta from the parity conditions).
- 3 attempts fail: revert any task.toml changes (`git checkout`), record exactly what failed. The policy hook remains the policing mechanism — same posture as the seatbelt harness.

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/wsvc-net-probe rebuild-kit-workspace/harbor-spike/SPIKE-NOTES.md
git commit -m "feat(harbor-spike): network allowlist experiment outcome"
```

---

### Task 9: SPIKE-REPORT.md finalization and go/no-go

**Files:**
- Modify: `rebuild-kit-workspace/harbor-spike/SPIKE-REPORT.md` (prepend narrative above the generated parity table)
- Modify: memory file `rebuild-kit-project-state.md` (project memory, not repo)

**Interfaces:**
- Consumes: SPIKE-NOTES.md from Tasks 5–8, the parity report, the spec's four open questions.

- [ ] **Step 1: Write the narrative sections**

Prepend to `SPIKE-REPORT.md`:
1. **Verdict** — go / no-go / go-with-caveats for migrating evals 1–2, one paragraph.
2. **Open questions answered** (from the spec): arm modeling in practice; fixture injection (build-context staging + cleanliness gate — worked/didn't, image rebuild cost per fixture change); isolation equivalence (container absence + build-then-probe gate + sanitized runtime payloads vs seatbelt; Task 8 outcome if run; residual risk stated); separate-verifier mechanics (the artifacts declaration + sentinel, exactly as configured, plus any permission-preservation caveats).
3. **Both scales, explicitly:** the mechanical parity table is the verdict basis; print the analyst-graded iteration-2 context (10/10 vs 4/10) beside the mechanical references (10/11 vs 3/11, 2 nulls) so no reader conflates them.
4. **Harbor rough edges** — from SPIKE-NOTES.md (include the stale-docs traps confirmed from source: `reward.json`/`result.json` singular; the run-phase-only `extra_allowed_hosts`; anything new).
5. **Pinned versions and image IDs** — harbor 0.20.0, claude CLI version from a trial's `agent/setup/` logs, docker version, `jobs/parity/image_ids.json` contents.
6. **What migration of evals 1–2 would take** — task-dir count, eval-1's `files_by_config` (per-arm fixtures) and eval-3-style `no_skill_any_arm` needing per-arm task variants or agent flags — one paragraph of honest scoping, referencing `run_arm.py`'s `eval_files()`.

- [ ] **Step 2: Self-check the report**

Every claim must trace to a file in `jobs/`, `scratch/`, or SPIKE-NOTES.md. No "should work" phrasing — only observed results.

- [ ] **Step 3: Commit and update project memory**

```bash
cd /Users/nicholasstelter/Code/skills/rebuild-kit
git add rebuild-kit-workspace/harbor-spike/SPIKE-REPORT.md rebuild-kit-workspace/harbor-spike/SPIKE-NOTES.md
git commit -m "docs(harbor-spike): spike report with parity verdict and go/no-go"
```
Then update the `rebuild-kit-project-state` memory: spike outcome + pointer to SPIKE-REPORT.md; note the seatbelt harness remains authoritative until a migration decision.

---

## Self-review notes (deliberate deviations, with reasons)

- **Same-container verification fallback** (spec §4's error path): not pre-built. If Task 5 proves the artifacts mechanism cannot carry `/app/work`, flip `environment_mode` to shared, accept that `tests/` enters the agent container only at verify time (post-run), and record the isolation implication in SPIKE-NOTES.md.
- **`grade_checks.py` `find_workspace` recursion**: pointing it at `/app/work` (containing both `ticketd/` and the agent's rewrite root) matches how the seatbelt harness grades staged run dirs.
- **Harbor job-level `metrics` unused**: report.py reads per-trial `reward.json` directly (and 0.20.0's stock `mean` metric aggregates multi-key rewards per key anyway — the v1 rationale was stale and is corrected in the spec).
- **Fixture staged from the working tree, not re-cloned from the bundle**: the working tree's `.git` *is* the bundle-restored history, and `prepare_task.py`'s porcelain check guarantees no uncommitted drift — equivalent guarantee, one less moving part.
