#!/usr/bin/env python3
"""P1 static inventory: file tree, module & dependency graph, route map, DDL discovery,
complexity approximation, churn hotspots. Writes inventory.json + hotspots.md at the root.

Usage: inventory.py [--root REWRITE_ROOT]   (default: walk up from cwd for rebuild.json)
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rk_common import LANG_BY_EXT, die, find_root, iter_source_files, load_layout, run

IMPORT_PATTERNS = {
    "python": [re.compile(r"^\s*from\s+([\w.]+)\s+import"), re.compile(r"^\s*import\s+([\w.]+)")],
    "javascript": [re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
                   re.compile(r"""from\s+['"]([^'"]+)['"]"""),
                   re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""")],
}
IMPORT_PATTERNS["typescript"] = IMPORT_PATTERNS["javascript"]

# (framework, regex, method-group-or-None, path-group)
ROUTE_PATTERNS = [
    ("flask", re.compile(r"@\w+\.route\(\s*['\"]([^'\"]+)['\"](?:.*methods\s*=\s*\[([^\]]*)\])?"), 2, 1),
    ("flask", re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]"), 1, 2),
    ("fastapi", re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]"), 1, 2),
    ("express", re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete|all|use)\(\s*['\"]([^'\"]+)['\"]"), 1, 2),
    ("django", re.compile(r"\b(?:path|re_path|url)\(\s*r?['\"]([^'\"]+)['\"]"), None, 1),
]

BRANCH_KEYWORDS = re.compile(
    r"\b(if|elif|else if|for|while|case|when|catch|except|rescue|\?\?|&&|\|\|)\b|\?[^.:]")


def analyze_file(path, base):
    rel = str(path.relative_to(base))
    lang = LANG_BY_EXT.get(path.suffix, "other")
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    imports = []
    for pat in IMPORT_PATTERNS.get(lang, []):
        for line in lines:
            m = pat.search(line)
            if m:
                imports.append(m.group(1))
    routes = []
    for fw, pat, mg, pg in ROUTE_PATTERNS:
        for i, line in enumerate(lines, 1):
            m = pat.search(line)
            if m:
                method = (m.group(mg) if mg and m.group(mg) else "GET").upper().strip("'\" ")
                routes.append({"framework": fw, "method": method, "path": m.group(pg),
                               "file": rel, "line": i, "detected": "pattern"})
    complexity = len(BRANCH_KEYWORDS.findall(text))
    return {"path": rel, "lang": lang, "loc": len(lines), "imports": sorted(set(imports)),
            "routes": routes, "complexity": complexity}


def resolve_edges(files):
    """Map import strings to in-tree files (best effort); rest are external deps."""
    by_stem = defaultdict(list)
    for f in files:
        p = Path(f["path"])
        by_stem[p.stem].append(f["path"])
        by_stem[str(p.with_suffix("")).replace("/", ".")].append(f["path"])
    edges, external = [], set()
    for f in files:
        for imp in f["imports"]:
            key = imp.lstrip("./").replace("/", ".").split(".")[-1] if "/" in imp else imp.split(".")[-1]
            targets = by_stem.get(key) or by_stem.get(imp.replace("/", "."))
            if targets:
                edges.append({"from": f["path"], "to": targets[0], "import": imp})
            else:
                external.add(imp.split("/")[0].split(".")[0])
    return edges, sorted(external)


def churn(legacy):
    code, out = run(["git", "-C", str(legacy), "log", "--numstat", "--format="])
    if code != 0:
        return None
    counts = defaultdict(int)
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit():
            counts[parts[2]] += int(parts[0]) + int(parts[1])
    return dict(counts)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else find_root()
    if not root or not (root / "rebuild.json").exists():
        die("no rebuild.json found — run scaffold.py first (P0)")
    cfg, legacy, _ = load_layout(root)

    files = [a for p in iter_source_files(legacy) if (a := analyze_file(p, legacy))]
    if not files:
        die(f"no source files found under {legacy}")
    edges, external = resolve_edges(files)
    routes = [r for f in files for r in f["routes"]]
    ddl = [str(p.relative_to(legacy)) for p in legacy.rglob("*.sql") if ".git" not in p.parts]
    migrations = sorted({str(p.relative_to(legacy)) for p in legacy.rglob("*migration*")
                         if p.is_dir() and ".git" not in p.parts})
    ch = churn(legacy)

    # coverage assertion: every discovered source file is in the inventory
    walked = {str(p.relative_to(legacy)) for p in iter_source_files(legacy)}
    inventoried = {f["path"] for f in files}
    assert walked == inventoried, f"coverage gap: {walked ^ inventoried}"

    notes = []
    if ch is None:
        notes.append("no git history in legacy tree: churn unavailable, hotspots are complexity-only")
    sparse = [f["path"] for f in files if f["lang"] not in IMPORT_PATTERNS and f["lang"] not in ("sql", "shell", "other")]
    if sparse:
        notes.append(f"generic scanning only (weaker dep graph) for: {sorted(set(sparse))[:10]}")

    inv = {"legacy_ref": cfg["legacy_ref"], "file_count": len(files),
           "total_loc": sum(f["loc"] for f in files),
           "files": files, "dependency_edges": edges, "external_deps": external,
           "routes": routes, "ddl_files": ddl, "migration_dirs": migrations,
           "churn": ch, "notes": notes}
    (root / "inventory.json").write_text(json.dumps(inv, indent=2) + "\n")

    scored = sorted(files, key=lambda f: (ch.get(f["path"], 0) if ch else 0) * max(f["complexity"], 1)
                    or f["complexity"], reverse=True)
    lines = ["# Hotspots", ""]
    if ch is None:
        lines.append("> No git history — complexity-only ranking (see inventory.json notes).\n")
    lines.append("| file | loc | complexity | churn | why it's hot |")
    lines.append("|---|---|---|---|---|")
    for f in scored[:15]:
        lines.append(f"| {f['path']} | {f['loc']} | {f['complexity']} | "
                     f"{ch.get(f['path'], '—') if ch else '—'} | <FILL: one line> |")
    (root / "hotspots.md").write_text("\n".join(lines) + "\n")

    print(json.dumps({"files": len(files), "loc": inv["total_loc"], "routes": len(routes),
                      "edges": len(edges), "ddl_files": ddl, "notes": notes}, indent=2))
    print("\nNext: spot-check the route map against entrypoints (add missed routes with "
          "detected: manual), sanity-check orphan modules, fill hotspots.md 'why' column.")


if __name__ == "__main__":
    main()
