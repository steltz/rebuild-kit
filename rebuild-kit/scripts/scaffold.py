#!/usr/bin/env python3
"""P0 scaffolder: rewrite-root layout, rebuild.json, legacy pin + read-only guard,
CLAUDE.md skeletons, root git repo with initial commit.

Usage:
  scaffold.py --root REWRITE_ROOT --legacy-dir NAME [--modern-dir modern]
              [--legacy-src PATH]   # clone/copy the legacy app into the root first

The legacy tree must already sit inside the root at --legacy-dir, or be provided
via --legacy-src (git clone if it's a repo, rsync-style copy otherwise).
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rk_common import die, run

LAYOUT_DIRS = [
    "docs/domain", "docs/features", "docs/contracts/schemas", "docs/contracts/fixtures",
    "docs/migration", "verification/replay/traces", "verification/replay/corpus",
    "verification/characterization", "verification/harness", "audit", "workflows",
    "guide/briefs",
]

SEED_FILES = {
    "docs/do-not-port.md": "# Do Not Port\n\n<!-- Negative space. Each entry: what, evidence "
                           "(zero-traffic + zero-references / PB-nnn), provenance. -->\n",
    "docs/open-questions.md": "# Open Questions — ASK register & PB proposals\n\n"
                              "<!-- see skill references/templates/open-questions.md -->\n",
    "backlog.md": "# Backlog\n\n<!-- Written in P8: milestones M0..Mn, ordered work orders. -->\n",
}

PRECOMMIT = """#!/bin/sh
# rebuild-kit guard: the legacy tree is read-only evidence.
# The very first commit (no HEAD yet) is the scaffold commit that adds legacy/
# for the first time — that's the pin, not a modification, so it's allowed.
# Every commit after that must not touch legacy/ at all.
LEGACY_DIR="{legacy}"
if git rev-parse --verify -q HEAD >/dev/null; then
  if git diff --cached --name-only | grep -q "^$LEGACY_DIR/"; then
    echo "REJECTED: staged changes under $LEGACY_DIR/ — the legacy tree is read-only evidence." >&2
    echo "If legacy itself must change, that happens upstream; re-pin deliberately." >&2
    exit 1
  fi
fi
exit 0
"""

CLAUDE_SKELETON = """# Rewrite Root — <FILL: system name>

<!-- P0: fill from skill references/templates/root-claude-md.md. Scaffold marker: FILL -->
"""

MODERN_CLAUDE_SKELETON = """# {modern}/ — Target Application

<!-- P0/P8: fill from skill references/templates/modern-claude-md.md. -->
## Target stack
PENDING (blocks P8/M0)
"""


def tree_hash(base: Path) -> str:
    """Deterministic content hash for an unversioned legacy tree."""
    h = hashlib.sha256()
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.parts:
            h.update(str(p.relative_to(base)).encode())
            h.update(p.read_bytes())
    return "tree-" + h.hexdigest()


def pin_legacy(legacy: Path):
    """Return (ref, method) for the legacy tree.

    `legacy` must be the ROOT of its own git working tree, not merely a
    subdirectory of some ancestor repo (e.g. the rewrite root itself, or a
    repo the whole workspace happens to live inside) — otherwise "git
    rev-parse HEAD" silently walks up and pins to an unrelated SHA that has
    nothing to do with the legacy app's actual content.
    """
    code, top = run(["git", "-C", str(legacy), "rev-parse", "--show-toplevel"])
    if code == 0 and Path(top.strip()).resolve() == legacy.resolve():
        code, out = run(["git", "-C", str(legacy), "rev-parse", "HEAD"])
        if code == 0:
            return out.strip(), "sha-recorded-clone"
    return tree_hash(legacy), "unversioned-snapshot"


def strip_write(base: Path):
    for p in base.rglob("*"):
        if ".git" in p.parts:
            continue
        try:
            p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--legacy-dir", required=True, help="name of the legacy dir inside the root")
    ap.add_argument("--modern-dir", default="modern")
    ap.add_argument("--legacy-src", help="path to legacy app to bring into the root")
    ap.add_argument("--no-chmod", action="store_true",
                    help="skip stripping write permissions on the legacy tree")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if (root / "rebuild.json").exists():
        die(f"{root}/rebuild.json already exists — this is resume/spec-patch territory, "
            "not scaffolding. See references/phases/spec-patch.md.")
    root.mkdir(parents=True, exist_ok=True)

    legacy = root / args.legacy_dir
    if args.legacy_src and not legacy.exists():
        src = Path(args.legacy_src).resolve()
        if not src.is_dir():
            die(f"--legacy-src {src} is not a directory")
        if (src / ".git").exists():
            run(["git", "clone", "--no-hardlinks", str(src), str(legacy)], check=True)
        else:
            shutil.copytree(src, legacy)
    if not legacy.is_dir():
        die(f"legacy dir {legacy} not found — place the app there or pass --legacy-src")

    ref, method = pin_legacy(legacy)

    for d in LAYOUT_DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / args.modern_dir).mkdir(exist_ok=True)

    for rel, content in SEED_FILES.items():
        p = root / rel
        if not p.exists():
            p.write_text(content)
    if not (root / "CLAUDE.md").exists():
        (root / "CLAUDE.md").write_text(CLAUDE_SKELETON)
    mc = root / args.modern_dir / "CLAUDE.md"
    if not mc.exists():
        mc.write_text(MODERN_CLAUDE_SKELETON.format(modern=args.modern_dir))
    if not (root / "ledger.json").exists():
        (root / "ledger.json").write_text(json.dumps(
            {"milestones": [], "work_orders": [],
             "audit": {"claims_confirmed_pct": None, "branch_coverage_pct": None,
                       "problem_coverage_pct": None, "demotion_rate": None}}, indent=2))

    rebuild = {
        "skill_version": "1.0",
        "created": date.today().isoformat(),
        "layout": {"legacy_dir": args.legacy_dir, "modern_dir": args.modern_dir},
        "legacy_ref": ref,
        "legacy_pin_method": method,
        "target_stack": {"language": None, "framework": None, "database": None,
                         "decided_by": "pending", "rationale": None},
        "evidence": {"runtime_ingestion": "inactive", "data_census": "inactive",
                     "trace_capture_t1": "inactive",
                     "notes": "set active per source granted in intake (P0/P2)"},
        "status": "generating",
        "phases_complete": [],
    }
    (root / "rebuild.json").write_text(json.dumps(rebuild, indent=2) + "\n")

    # git repo + read-only guard
    if not (root / ".git").exists():
        run(["git", "init", "-q", str(root)], check=True)
    hooks = root / ".githooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text(PRECOMMIT.format(legacy=args.legacy_dir))
    hook.chmod(0o755)
    run(["git", "-C", str(root), "config", "core.hooksPath", ".githooks"], check=True)
    gi = root / ".gitignore"
    if not gi.exists():
        gi.write_text("__pycache__/\nnode_modules/\n*.pyc\n")

    if not args.no_chmod:
        strip_write(legacy)

    run(["git", "-C", str(root), "add", "-A"], check=True)
    code, _ = run(["git", "-C", str(root), "commit", "-q", "-m",
                   "chore: scaffold rewrite root (rebuild-kit P0)"])
    if code != 0:
        print("note: initial commit failed (git identity not configured?) — commit manually.",
              file=sys.stderr)

    print(json.dumps({"root": str(root), "legacy_ref": ref, "pin_method": method,
                      "layout_dirs": len(LAYOUT_DIRS)}, indent=2))
    print("\nNext: fill CLAUDE.md skeletons (FILL markers), conduct the intake interview, "
          "write docs/problem-brief.md, then verify the guard rejects a write under "
          f"{args.legacy_dir}/.")


if __name__ == "__main__":
    main()
