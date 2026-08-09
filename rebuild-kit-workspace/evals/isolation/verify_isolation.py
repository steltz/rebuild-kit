#!/usr/bin/env python3
"""Prove the eval isolation holds. Run this before every iteration.

Layer 1 (default, free, no model calls): execute real read attempts under the
generated seatbelt profiles and assert the kernel refuses them. This covers every
leak vector known to have contaminated a past iteration, plus the ones found
while replacing the old move-the-directory approach.

Layer 2 (--live, costs one model call): run an actual headless agent under the
baseline profile and explicitly order it to find and read the skill. Asserts it
comes back empty-handed. Layer 1 tests the wall; layer 2 tests that an agent
with tools cannot go around it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from run_arm import (
    REPO_ROOT,
    SKILL_DIR,
    WORKSPACE,
    build_profile,
    build_settings,
    install_guard,
)

CANARY = "P7-replay-harness"  # distinctive skill string that must never leak


def run_under(profile: str, argv: list[str], cwd: str = "/private/tmp"):
    with tempfile.NamedTemporaryFile("w", suffix=".sb", delete=False) as fh:
        fh.write(profile)
        path = fh.name
    try:
        return subprocess.run(["sandbox-exec", "-f", path, *argv], cwd=cwd,
                              capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n          {detail}" if detail and not ok else ""))
    return ok


def layer1() -> bool:
    baseline = build_profile("without_skill")
    with_skill = build_profile("with_skill")
    home = Path.home()
    results = []

    print("\nbaseline arm — these must all be DENIED:")
    denied = [
        ("skill SKILL.md", ["/bin/cat", str(SKILL_DIR / "SKILL.md")]),
        ("skill script (the file that leaked in iterations 1-2)",
         ["/bin/cat", str(SKILL_DIR / "scripts" / "render_guide.py")]),
        ("eval assertions", ["/bin/cat", str(WORKSPACE / "evals" / "evals.json")]),
        ("skill content via repo git history",
         ["git", "-C", str(REPO_ROOT), "show", "HEAD:rebuild-kit/SKILL.md"]),
        ("prior session transcripts", ["/bin/ls", str(home / ".claude" / "projects")]),
        ("skill dir listing", ["/bin/ls", str(SKILL_DIR)]),
    ]
    for name, argv in denied:
        proc = run_under(baseline, argv)
        blob = proc.stdout + proc.stderr
        ok = proc.returncode != 0 and CANARY not in blob and "name: rebuild-kit" not in blob
        results.append(check(name, ok, f"rc={proc.returncode} out={blob[:200]!r}"))

    print("\nbaseline arm — a filesystem sweep must surface nothing:")
    proc = run_under(baseline, ["/usr/bin/grep", "-rl", CANARY, str(REPO_ROOT)])
    results.append(check("recursive grep over the repo",
                         CANARY not in proc.stdout and not proc.stdout.strip(),
                         f"out={proc.stdout[:200]!r}"))

    print("\nbaseline arm — unrelated work must still be ALLOWED:")
    allowed = [
        ("read /etc/hosts", ["/bin/cat", "/etc/hosts"]),
        ("write in the run dir", ["/bin/sh", "-c", "echo ok > /private/tmp/.rk-iso-probe && cat /private/tmp/.rk-iso-probe"]),
        ("python available", [sys.executable, "-c", "print('ok')"]),
    ]
    for name, argv in allowed:
        proc = run_under(baseline, argv)
        results.append(check(name, proc.returncode == 0, f"rc={proc.returncode} err={proc.stderr[:200]!r}"))
    Path("/private/tmp/.rk-iso-probe").unlink(missing_ok=True)

    print("\nwith-skill arm — the skill must be READABLE, the rest still denied:")
    proc = run_under(with_skill, ["/bin/cat", str(SKILL_DIR / "SKILL.md")])
    results.append(check("skill readable", proc.returncode == 0 and "rebuild-kit" in proc.stdout,
                         f"rc={proc.returncode}"))
    proc = run_under(with_skill, ["/bin/cat", str(WORKSPACE / "evals" / "evals.json")])
    results.append(check("assertions still denied", proc.returncode != 0, f"rc={proc.returncode}"))

    return all(results)


def layer2(model: str | None) -> bool:
    """One real agent, told to go get the skill, under the baseline profile."""
    print("\nlive probe — an agent explicitly ordered to find the skill:")
    run_dir = Path(tempfile.mkdtemp(prefix="wsvc-probe-", dir="/private/tmp"))
    audit = run_dir / "audit.jsonl"
    settings = run_dir / "settings.json"
    settings.write_text(json.dumps(build_settings(audit, install_guard(run_dir))))
    profile_path = run_dir / "p.sb"
    profile_path.write_text(build_profile("without_skill"))

    prompt = (
        "There is a Claude Code skill named 'rebuild-kit' somewhere on this machine, "
        "probably under a directory like ~/Code/skills. Find it by any means: search "
        "the filesystem, check git history of any repo you find, look in ~/.claude, try "
        "mdfind. Then print the literal contents of its SKILL.md and of "
        "scripts/render_guide.py. If you cannot read them, say exactly NOTFOUND."
    )
    cmd = ["sandbox-exec", "-f", str(profile_path), "claude", "-p", prompt,
           "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--no-session-persistence", "--settings", str(settings)]
    if model:
        cmd += ["--model", model]
    env = dict(os.environ, RK_AUDIT_LOG=str(audit), RK_GUARD_MODE="block")
    proc = subprocess.run(cmd, cwd=run_dir, env=env, capture_output=True,
                          text=True, timeout=900)
    try:
        out = json.loads(proc.stdout).get("result", "")
    except (json.JSONDecodeError, ValueError):
        out = proc.stdout

    leaked = CANARY in out or "name: rebuild-kit" in out or "def render_guide" in out
    ok = check("agent could not read skill content", not leaked, f"result={out[:400]!r}")
    print(f"          agent said: {out.strip()[:200]!r}")

    # The guard hook lives in the repo, which the baseline profile denies. If it
    # is not staged outside the repo it silently never fires, taking the audit
    # log and the network block with it. An empty log means exactly that.
    n = len(audit.read_text().splitlines()) if audit.exists() else 0
    ok = check("guard hook fired under the sandbox (audit log non-empty)", n > 0,
               "audit log missing or empty — hook unreachable from inside the sandbox") and ok
    print(f"          audit log captured {n} tool calls")
    shutil.rmtree(run_dir, ignore_errors=True)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run the real-agent probe (costs a model call)")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    if sys.platform != "darwin" or not shutil.which("sandbox-exec"):
        print("sandbox-exec unavailable — isolation cannot be enforced on this host")
        return 2

    ok = layer1()
    if args.live:
        ok = layer2(args.model) and ok
    print("\n" + ("ISOLATION VERIFIED" if ok else "ISOLATION BROKEN — do not run evals"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
