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

Fixtures need the same treatment for a different reason. Their .git dirs are not
committable either, so a fresh clone gets fixtures with no history — and git
then walks up and resolves `rev-parse HEAD` to the outer repo instead of
failing, which makes the legacy_ref assertions compare against the wrong SHA.
Fixtures must keep working locally, so bundle them without removing anything:

  git_bundles.py pack --keep fixtures          # commit the bundles
  git_bundles.py unpack fixtures               # once, after cloning

A fixture staged by copying an earlier eval output has the same hole: the files
came across but the history did not. graft re-attaches it, and refuses unless
the worktree matches the bundle exactly. Graft innermost repos first, so a
nested legacy tree is a real gitlink by the time its parent is checked:

  git_bundles.py graft <bundle> <target-dir>
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


def pack(root: Path, keep: bool = False) -> int:
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

        if not keep:
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


def restore_into(repo: Path, bundle: Path, head_sha: str, head_branch: str) -> str | None:
    """Give `repo` the history in `bundle`. Returns an error string, or None."""
    bundle = bundle.resolve()  # fetch runs with cwd=repo, so this must be absolute
    rc, msg = git("init", "--quiet", str(repo))
    if rc != 0:
        return f"init: {msg}"
    git("symbolic-ref", "HEAD", PLACEHOLDER, cwd=repo)
    rc, msg = git("fetch", "--quiet", str(bundle), "+refs/*:refs/*", cwd=repo)
    if rc != 0:
        return f"fetch: {msg.splitlines()[-1] if msg else rc}"

    if head_branch and head_branch != "HEAD":
        git("symbolic-ref", "HEAD", f"refs/heads/{head_branch}", cwd=repo)
    else:
        git("update-ref", "--no-deref", "HEAD", head_sha, cwd=repo)
    git("reset", "--quiet", cwd=repo)  # rebuild the index; worktree untouched

    rc, head = git("rev-parse", "HEAD", cwd=repo)
    if rc != 0 or head != head_sha:
        return f"verify: expected {head_sha[:12]}, got {head[:12]}"
    return None


def graft(bundle: Path, repo: Path) -> int:
    """Attach a bundle's history to a directory staged elsewhere.

    Fixtures are frozen copies of earlier eval outputs. Copying the files leaves
    the history behind, and a workspace with no .git does not fail loudly — git
    walks up to the enclosing repo, so the pinned legacy_ref silently compares
    against the wrong SHA. This re-attaches the real history to such a copy.

    Refuses unless the worktree matches the history exactly, so a stale or
    mismatched bundle cannot be grafted onto a tree it does not describe.
    """
    if not bundle.is_file():
        raise SystemExit(f"no such bundle: {bundle}")
    if not repo.is_dir():
        raise SystemExit(f"not a directory: {repo}")
    if (repo / ".git").exists():
        print(f"{repo} already has .git — nothing to do")
        return 0

    rc, heads = git("bundle", "list-heads", str(bundle))
    if rc != 0:
        raise SystemExit(f"unreadable bundle: {heads}")
    branches = [ln.split(" refs/heads/")[1].strip()
                for ln in heads.splitlines() if " refs/heads/" in ln]
    shas = {ln.split(" refs/heads/")[1].strip(): ln.split()[0]
            for ln in heads.splitlines() if " refs/heads/" in ln}
    if len(branches) != 1:
        raise SystemExit(f"bundle has {len(branches)} branches; expected exactly one: {branches}")
    branch = branches[0]

    err = restore_into(repo, bundle, shas[branch], branch)
    if err:
        shutil.rmtree(repo / ".git", ignore_errors=True)
        raise SystemExit(f"graft failed ({err}); left {repo} untouched")

    # The decisive check: a clean status means the files on disk are exactly
    # what this history says they should be.
    rc, dirty = git("status", "--porcelain", cwd=repo)
    if dirty.strip():
        n = len(dirty.strip().splitlines())
        shutil.rmtree(repo / ".git", ignore_errors=True)
        raise SystemExit(
            f"graft rejected: worktree differs from the bundle's history in {n} path(s).\n"
            f"This bundle does not describe this tree. Left {repo} untouched.\n"
            + "\n".join("  " + ln for ln in dirty.strip().splitlines()[:10]))

    # A bundle carries refs and objects, not config. The scaffolder points
    # core.hooksPath at .githooks to arm the legacy-tree guard, so a grafted
    # workspace would look intact while its protection silently did nothing.
    hooks_note = ""
    if (repo / ".githooks").is_dir():
        rc, existing = git("config", "--local", "core.hooksPath", cwd=repo)
        if rc != 0 or not existing.strip():
            git("config", "core.hooksPath", ".githooks", cwd=repo)
            hooks_note = "\n  restored core.hooksPath=.githooks (not carried by bundles)"

    _, head = git("rev-parse", "HEAD", cwd=repo)
    print(f"grafted {bundle.name} onto {repo}\n"
          f"  HEAD={head[:12]} branch={branch}  worktree clean{hooks_note}")
    return 0


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

        err = restore_into(repo, bundle, entry["head_sha"], entry["head_branch"])
        if err:
            print(f"FAIL {entry['path']}: {err}")
            failures += 1
            continue
        _, head = git("rev-parse", "HEAD", cwd=repo)
        print(f"unpacked {entry['path']}  HEAD={head[:12]}")

    print(f"\n{len(manifest) - failures}/{len(manifest)} restored")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["pack", "unpack", "graft"])
    ap.add_argument("iteration", help="directory to pack/unpack, or the bundle to graft")
    ap.add_argument("target", nargs="?", help="graft only: directory to attach the history to")
    ap.add_argument("--keep", action="store_true",
                    help="bundle without removing the .git dirs (use for fixtures, "
                         "which must stay runnable locally)")
    args = ap.parse_args()

    workspace = Path(__file__).resolve().parent.parent

    def resolve(p: str) -> Path:
        """Relative paths mean what they'd mean in the shell; fall back to
        workspace-relative so `pack iteration-3` works from anywhere."""
        q = Path(p)
        if q.is_absolute() or q.exists():
            return q
        return workspace / p

    if args.action == "graft":
        if not args.target:
            raise SystemExit("graft needs two arguments: <bundle> <target-dir>")
        return graft(resolve(args.iteration), resolve(args.target))

    root = resolve(args.iteration)
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    return pack(root, keep=args.keep) if args.action == "pack" else unpack(root)


if __name__ == "__main__":
    sys.exit(main())
