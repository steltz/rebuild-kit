#!/usr/bin/env python3
"""Pack/unpack the git repos embedded in eval outputs.

Eval outputs contain whole git repos: the rewrite roots the agent generated, and
copies of the legacy fixture. Git cannot commit a nested repo's files — it turns
the directory into a gitlink and the files vanish from the archive. Deleting the
history instead would be lossy, because grade_checks.py verifies the pinned
legacy_ref by running `git rev-parse HEAD` against it.

So the history is stored as a bundle (one file, ~20x smaller than the loose
object store) and the working files commit normally. `pack` never removes a .git
until it has cloned the bundle back and confirmed an identical HEAD.

  git_bundles.py pack   iteration-2-sonnet
  git_bundles.py unpack iteration-2-sonnet     # before re-grading
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BUNDLE_DIR = "_git_bundles"
MANIFEST = "manifest.json"
SEP = "__"
# git init checks out a branch, and git refuses to fetch into a checked-out
# branch. Parking HEAD on an unborn placeholder keeps every real ref fetchable.
PLACEHOLDER = "refs/heads/__bundle_restore__"


def git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def embedded_repos(root: Path) -> list[Path]:
    """Deepest first, so a nested repo is handled before its parent."""
    repos = [p.parent for p in root.rglob(".git") if p.is_dir()]
    return sorted(repos, key=lambda p: len(p.parts), reverse=True)


def key_for(root: Path, repo: Path) -> str:
    return str(repo.relative_to(root)).replace("/", SEP) + ".bundle"


def pack(root: Path) -> int:
    repos = embedded_repos(root)
    if not repos:
        print(f"no embedded repos under {root}")
        return 0
    out_dir = root / BUNDLE_DIR
    out_dir.mkdir(exist_ok=True)
    manifest = {}
    failures = 0

    for repo in repos:
        bundle = out_dir / key_for(root, repo)
        rc, msg = git("bundle", "create", str(bundle), "--all", cwd=repo)
        if rc != 0:
            print(f"FAIL bundle  {repo}: {msg.splitlines()[-1] if msg else rc}")
            failures += 1
            continue

        rc, head = git("rev-parse", "HEAD", cwd=repo)
        if rc != 0:
            print(f"FAIL rev-parse {repo}")
            failures += 1
            continue
        # Which branch HEAD was on ("HEAD" if it was detached). Recording it
        # here is what lets unpack restore the exact same state instead of
        # guessing a branch out of the bundle's ref list.
        _, branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)

        # Prove the bundle restores before destroying the source of truth.
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "probe"
            rc, msg = git("clone", "--quiet", str(bundle), str(probe))
            if rc != 0:
                print(f"FAIL restore {repo}: {msg.splitlines()[-1] if msg else rc}")
                failures += 1
                continue
            rc, restored = git("rev-parse", "HEAD", cwd=probe)
            if rc != 0 or restored != head:
                print(f"FAIL verify  {repo}: {head[:12]} != {restored[:12]}")
                failures += 1
                continue

        shutil.rmtree(repo / ".git")
        manifest[bundle.name] = {
            "path": str(repo.relative_to(root)),
            "head_sha": head,
            "head_branch": branch,
        }
        print(f"packed {repo.relative_to(root)}  HEAD={head[:12]}  "
              f"{bundle.stat().st_size // 1024}K")

    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\n{len(repos) - failures}/{len(repos)} packed into {out_dir}")
    return 1 if failures else 0


def unpack(root: Path) -> int:
    out_dir = root / BUNDLE_DIR
    if not out_dir.is_dir():
        print(f"no {BUNDLE_DIR}/ under {root}")
        return 1
    manifest_path = out_dir / MANIFEST
    if not manifest_path.is_file():
        print(f"no {MANIFEST} in {out_dir}")
        return 1
    manifest = json.loads(manifest_path.read_text())
    failures = 0

    for name, entry in sorted(manifest.items()):
        bundle = out_dir / name
        repo = root / entry["path"]
        if not repo.is_dir():
            print(f"FAIL {entry['path']}: directory missing")
            failures += 1
            continue
        if (repo / ".git").exists():
            print(f"skip {entry['path']}: already has .git")
            continue

        rc, msg = git("init", "--quiet", str(repo))
        if rc != 0:
            print(f"FAIL init {entry['path']}: {msg}")
            failures += 1
            continue
        git("symbolic-ref", "HEAD", PLACEHOLDER, cwd=repo)
        rc, msg = git("fetch", "--quiet", str(bundle), "+refs/*:refs/*", cwd=repo)
        if rc != 0:
            print(f"FAIL fetch {entry['path']}: {msg.splitlines()[-1] if msg else rc}")
            failures += 1
            continue

        branch = entry["head_branch"]
        if branch and branch != "HEAD":
            git("symbolic-ref", "HEAD", f"refs/heads/{branch}", cwd=repo)
        else:
            git("update-ref", "--no-deref", "HEAD", entry["head_sha"], cwd=repo)
        git("reset", "--quiet", cwd=repo)  # rebuild the index; worktree untouched

        rc, head = git("rev-parse", "HEAD", cwd=repo)
        if rc != 0 or head != entry["head_sha"]:
            print(f"FAIL verify {entry['path']}: {entry['head_sha'][:12]} != {head[:12]}")
            failures += 1
            continue
        print(f"unpacked {entry['path']}  HEAD={head[:12]}")

    print(f"\n{len(manifest) - failures}/{len(manifest)} restored")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["pack", "unpack"])
    ap.add_argument("iteration", help="iteration dir, relative to the workspace or absolute")
    args = ap.parse_args()

    root = Path(args.iteration)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / args.iteration
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    return pack(root) if args.action == "pack" else unpack(root)


if __name__ == "__main__":
    sys.exit(main())
