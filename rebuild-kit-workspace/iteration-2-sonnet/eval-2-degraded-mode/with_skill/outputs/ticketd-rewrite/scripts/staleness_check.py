#!/usr/bin/env python3
"""Staleness check: has upstream legacy moved past the pin, and do any changes touch
line ranges cited by workspace artifacts?

Usage: staleness_check.py [--root ROOT]
Scans docs/ + verification/ for citations like `legacy/src/x.py:88-114`, diffs
legacy_ref..HEAD in the legacy clone, and reports cited ranges that overlap changed hunks.
Cheap by design — no monitoring machinery.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rk_common import die, find_root, load_layout, run

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def collect_citations(root, legacy_dirname):
    cite_re = re.compile(rf"{re.escape(legacy_dirname)}/([\w./\-]+):(\d+)(?:-(\d+))?")
    cites = defaultdict(list)
    for base in ("docs", "verification", "audit", "guide", "backlog.md", "CLAUDE.md"):
        p = root / base
        files = [p] if p.is_file() else (p.rglob("*.md") if p.is_dir() else [])
        for f in files:
            for m in cite_re.finditer(f.read_text(errors="replace")):
                start = int(m.group(2))
                end = int(m.group(3) or start)
                cites[m.group(1)].append((start, end, str(f.relative_to(root))))
    return cites


def changed_hunks(legacy, pin):
    code, out = run(["git", "-C", str(legacy), "diff", "--unified=0", pin, "HEAD"])
    if code != 0:
        return None
    hunks, current = defaultdict(list), None
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif current and (m := HUNK_RE.match(line)):
            start = int(m.group(1))
            hunks[current].append((start, start + int(m.group(2) or 1) - 1))
    return hunks


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else find_root()
    if not root:
        die("no rebuild.json found")
    cfg, legacy, _ = load_layout(root)
    pin = cfg["legacy_ref"]

    if cfg["legacy_pin_method"] == "unversioned-snapshot":
        print(json.dumps({"stale": "unknown",
                          "note": "legacy tree is an unversioned snapshot — no upstream to compare"}))
        return
    code, head = run(["git", "-C", str(legacy), "rev-parse", "HEAD"])
    if code != 0:
        die(f"cannot read git HEAD in {legacy}")
    head = head.strip()
    if head == pin:
        print(json.dumps({"stale": False, "pin": pin, "head": head,
                          "note": "legacy clone is at the pin"}))
        return

    hunks = changed_hunks(legacy, pin)
    cites = collect_citations(root, cfg["layout"]["legacy_dir"])
    hits = []
    for path, ranges in (hunks or {}).items():
        for cs, ce, src in cites.get(path, []):
            for hs, he in ranges:
                if cs <= he and hs <= ce:
                    hits.append({"file": path, "cited_range": f"{cs}-{ce}",
                                 "changed_range": f"{hs}-{he}", "cited_from": src})
    print(json.dumps({"stale": True, "pin": pin, "head": head,
                      "changed_files": len(hunks or {}), "citations_scanned":
                          sum(len(v) for v in cites.values()),
                      "cited_ranges_touched": hits,
                      "action": "citations remain valid AGAINST THE PIN; if re-pinning, "
                                "re-verify the listed artifacts first"}, indent=2))


if __name__ == "__main__":
    main()
