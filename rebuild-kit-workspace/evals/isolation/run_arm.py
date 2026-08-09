#!/usr/bin/env python3
"""Run one eval arm (one eval x one config) under enforced isolation.

Replaces the old manual procedure, which isolated the baseline arm by physically
moving the skill directory out of the repo for the duration of the run. That was
unsound in three ways: a crash left the developer's tree mutilated, the two arms
could not run concurrently, and it only hid the skill's own directory while
leaving the same content readable via the repo's git history and via prior
session transcripts.

Isolation here is kernel-enforced instead. The executor runs under a seatbelt
profile that makes the leak vectors unreadable for real, so the guarantee does
not depend on the agent's incuriosity or on cleanup running.

Usage:
  run_arm.py --eval 0 --config without_skill --iteration iteration-3 --model sonnet
  run_arm.py --eval 0 --config with_skill  --iteration iteration-3 --model sonnet
  run_arm.py --eval 0 --config without_skill --iteration iteration-3 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent               # rebuild-kit-workspace/
REPO_ROOT = WORKSPACE.parent                 # repo root
SKILL_DIR = REPO_ROOT / "rebuild-kit"        # the skill under test
EVALS_JSON = WORKSPACE / "evals" / "evals.json"

# Run dirs are deliberately neutral: nothing in the path names the skill, so an
# agent inspecting its own cwd gets no hint that a skill exists to look for.
RUN_PARENT = Path("/private/tmp")
RUN_PREFIX = "wsvc-"

WITH_SKILL_SUFFIX = (
    "\n\nA skill that may help with this task is installed at {skill_dir}. "
    "Read {skill_dir}/SKILL.md first and follow it."
)

# Applied identically to both arms, before any skill mention.
#
# Iterations 1-2 ran executors through the Agent tool, which supplies this
# framing implicitly. `claude -p` does not, and the first iteration-3 attempt
# showed why that matters: the eval-0 baseline spent 17 turns and then stopped
# to ask which slug strategy to use, delivering no workspace at all. That
# measures willingness to ask a question, not the quality of the artifact the
# eval is about, and it would have made the arms incomparable to earlier runs.
AUTONOMY_FRAMING = (
    "\n\nYou are running autonomously as a background job. No human is available "
    "to answer questions during this run, and there is no one to reply to a "
    "clarifying question — so do not stop to ask one. Where something is genuinely "
    "undecided, make a defensible choice or record it as an open question in your "
    "deliverable, and keep going. Finish by producing the artifacts the task asks "
    "for, then close with a short report of what you produced and its limitations."
)


def build_profile(config: str, allow_skill: bool = True) -> str:
    """Generate the seatbelt profile for an arm.

    Everything is allowed except reads of the paths that carry skill content.
    Rules are order-sensitive: a later rule overrides an earlier one, which is
    how the with-skill arm re-opens the skill directory after the blanket repo
    deny.

    `allow_skill=False` keeps the skill denied even for the with_skill arm.
    Eval 3 needs that: it measures the generated workspace as a product, so both
    arms must run as a plain executor session with no generator skill available
    — the arms differ only in which workspace they were handed.
    """
    home = Path.home()
    lines = [
        "(version 1)",
        "(allow default)",
        "",
        ";; The whole project repo. Covers, in one rule: the skill implementation,",
        ";; the eval assertions in evals.json, outputs of prior with-skill runs, and",
        ";; the skill's full content inside .git objects.",
        f'(deny file-read* (subpath "{REPO_ROOT}"))',
        "",
        ";; Prior Claude sessions. Transcripts of earlier with-skill runs and the",
        ";; project memory both quote skill content verbatim. Runs use",
        ";; --no-session-persistence, so nothing here is needed.",
        f'(deny file-read* (subpath "{home / ".claude" / "projects"}"))',
        f'(deny file-read* (literal "{home / ".claude" / "history.jsonl"}"))',
    ]
    if config == "with_skill" and allow_skill:
        lines += [
            "",
            ";; This arm is supposed to read the skill; re-allow just that subtree.",
            ";; The rest of the repo (assertions, prior outputs) stays denied.",
            f'(allow file-read* (subpath "{SKILL_DIR}"))',
        ]
    return "\n".join(lines) + "\n"


def install_guard(dest_dir: Path) -> Path:
    """Copy the guard hook outside the repo before use.

    The sandbox profile denies reads of the whole repo, which includes this
    directory — so a hook referenced at its repo path cannot be executed by the
    very arm it is meant to police. Staging a copy in the (allowed) harness dir
    is what makes the audit log and the network block real for the baseline arm.
    """
    staged = dest_dir / "guard_hook.py"
    shutil.copy2(HERE / "guard_hook.py", staged)
    return staged


def build_settings(audit_log: Path, hook_path: Path) -> dict:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{sys.executable} {hook_path}",
                        }
                    ],
                }
            ]
        },
        # Defense in depth. The sandbox is the real enforcement; these deny rules
        # make the intent legible in the run record and stop the obvious paths
        # before a tool call is even attempted.
        "permissions": {
            "deny": [
                f"Read({SKILL_DIR}/**)",
                f"Read({WORKSPACE}/**)",
            ]
        },
        "_rk_audit_log": str(audit_log),
    }


def load_eval(eval_id: int) -> dict:
    data = json.loads(EVALS_JSON.read_text())
    for ev in data["evals"]:
        if ev["id"] == eval_id:
            return ev
    raise SystemExit(f"no eval with id {eval_id} in {EVALS_JSON}")


def eval_files(ev: dict, config: str) -> list[str]:
    """Fixtures for this arm.

    Most evals hand both arms the same fixture and vary only skill access. Eval 3
    inverts that: no arm gets the skill, and the arms differ by which prepared
    workspace they are asked to execute from, so the fixture is per-config.
    """
    by_config = ev.get("files_by_config")
    if by_config:
        if config not in by_config:
            raise SystemExit(f"eval {ev['id']} has no files_by_config entry for {config}")
        return by_config[config]
    return ev["files"]


def stage_run_dir(ev: dict, config: str) -> Path:
    run_dir = RUN_PARENT / f"{RUN_PREFIX}{uuid.uuid4().hex[:10]}"
    run_dir.mkdir(parents=True)
    for rel in eval_files(ev, config):
        src = WORKSPACE / rel
        if not src.exists():
            raise SystemExit(f"fixture missing: {src}")
        # copy2/copytree preserves .git, which eval-0 needs for its legacy_ref
        # assertion.
        shutil.copytree(src, run_dir / src.name, symlinks=True)
    return run_dir


def harness_dir(run_dir: Path) -> Path:
    """Harness bookkeeping lives outside the run dir so it can never be mistaken
    for agent output when the outputs are copied back for grading."""
    d = run_dir.parent / (run_dir.name + "-harness")
    d.mkdir(exist_ok=True)
    return d


def build_command(ev: dict, config: str, model: str | None,
                  profile_path: Path, settings_path: Path) -> list[str]:
    prompt = ev["prompt"] + AUTONOMY_FRAMING
    if config == "with_skill" and not ev.get("no_skill_any_arm"):
        prompt += WITH_SKILL_SUFFIX.format(skill_dir=SKILL_DIR)
    cmd = [
        "sandbox-exec", "-f", str(profile_path),
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--settings", str(settings_path),
    ]
    if model:
        cmd += ["--model", model]
    return cmd


def collect(stream_path: Path) -> dict:
    """Pull the final result record out of the stream-json transcript."""
    result = {}
    try:
        for line in stream_path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") == "result":
                result = rec
    except OSError:
        pass
    return result


def audit_summary(audit_log: Path) -> dict:
    calls, blocked, probes = 0, [], []
    if audit_log.exists():
        for line in audit_log.read_text(errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            calls += 1
            if rec.get("blocked"):
                blocked.append(rec)
            if rec.get("probe_hits"):
                probes.append(rec)
    return {
        "tool_calls": calls,
        "blocked_calls": len(blocked),
        "skill_probe_calls": len(probes),
        # A baseline run with probes is not necessarily contaminated — the
        # sandbox denied the reads — but the grader should look.
        "review_recommended": bool(blocked or probes),
        "probe_samples": [p["input"][:300] for p in probes[:10]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=int, required=True)
    ap.add_argument("--config", choices=["with_skill", "without_skill"], required=True)
    ap.add_argument("--iteration", required=True,
                    help="iteration dir name under the workspace, e.g. iteration-3")
    ap.add_argument("--model", default=None, help="model alias, e.g. sonnet / fable")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--keep-run-dir", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="stage everything and print the command without running it")
    args = ap.parse_args()

    if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
        raise SystemExit(
            "sandbox-exec unavailable: isolation cannot be enforced on this host. "
            "Refusing to run rather than produce a result that looks clean but isn't."
        )

    ev = load_eval(args.eval)
    allow_skill = not ev.get("no_skill_any_arm")
    run_dir = stage_run_dir(ev, args.config)
    hdir = harness_dir(run_dir)

    profile_path = hdir / "sandbox.sb"
    profile_path.write_text(build_profile(args.config, allow_skill))
    audit_log = hdir / "audit.jsonl"
    settings_path = hdir / "settings.json"
    settings_path.write_text(
        json.dumps(build_settings(audit_log, install_guard(hdir)), indent=2)
    )

    cmd = build_command(ev, args.config, args.model, profile_path, settings_path)

    if args.dry_run:
        print(json.dumps({"run_dir": str(run_dir), "harness": str(hdir),
                          "cmd": cmd}, indent=2))
        return 0

    env = dict(os.environ)
    env["RK_AUDIT_LOG"] = str(audit_log)
    # Block remote retrieval of the skill for any arm that is not supposed to
    # read it — which for a no_skill_any_arm eval means both arms.
    env["RK_GUARD_MODE"] = (
        "block" if (args.config == "without_skill" or not allow_skill) else "audit"
    )

    stream_path = hdir / "transcript.jsonl"
    started = time.time()
    with open(stream_path, "w") as out:
        proc = subprocess.run(cmd, cwd=run_dir, env=env, stdout=out,
                              stderr=subprocess.PIPE, timeout=args.timeout)
    elapsed_ms = int((time.time() - started) * 1000)

    result = collect(stream_path)
    summary = audit_summary(audit_log)
    dest = WORKSPACE / args.iteration / f"eval-{ev['id']}-{ev['name']}" / args.config
    (dest / "outputs").mkdir(parents=True, exist_ok=True)
    # An executor arm may install dependencies to run what it built. That output
    # is environment, not work product: eval 3's first run copied back a 4,300-file
    # .venv that buried the ~40 files a grader actually needs to read.
    # `pgdata` is the same class of thing one level further in: an eval-3 arm
    # booted Postgres to run the twin-boot harness and left 2,572 files of server
    # state behind. The logs and captured traces beside it are kept — those are
    # the evidence that verification actually ran.
    skip = shutil.ignore_patterns(
        ".venv", "venv", "env", "node_modules", "__pycache__", "*.pyc",
        ".pytest_cache", ".mypy_cache", "site-packages", "*.egg-info", ".tox",
        "pgdata", "*.sqlite3-journal", ".DS_Store",
    )
    for child in run_dir.iterdir():
        target = dest / "outputs" / child.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if child.is_dir():
            shutil.copytree(child, target, symlinks=True, ignore=skip)
        else:
            shutil.copy2(child, target)

    timing = {
        "duration_ms": result.get("duration_ms", elapsed_ms),
        "wall_ms": elapsed_ms,
        "total_tokens": (result.get("usage") or {}),
        "total_cost_usd": result.get("total_cost_usd"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error", proc.returncode != 0),
        "exit_code": proc.returncode,
    }
    (dest / "timing.json").write_text(json.dumps(timing, indent=2))
    (dest / "isolation.json").write_text(json.dumps({
        "enforced_by": "sandbox-exec (seatbelt)",
        "config": args.config,
        "skill_readable": args.config == "with_skill" and allow_skill,
        "profile": build_profile(args.config, allow_skill),
        "audit": summary,
    }, indent=2))
    shutil.copy2(stream_path, dest / "transcript.jsonl")
    if audit_log.exists():
        shutil.copy2(audit_log, dest / "audit.jsonl")
    (dest / "final_report.md").write_text(result.get("result", "") or "")

    if proc.stderr:
        (dest / "stderr.log").write_bytes(proc.stderr)

    if not args.keep_run_dir:
        shutil.rmtree(run_dir, ignore_errors=True)
        shutil.rmtree(hdir, ignore_errors=True)

    print(json.dumps({"dest": str(dest), "timing": timing, "audit": summary}, indent=2))
    return 0 if not timing["is_error"] else 1


if __name__ == "__main__":
    sys.exit(main())
