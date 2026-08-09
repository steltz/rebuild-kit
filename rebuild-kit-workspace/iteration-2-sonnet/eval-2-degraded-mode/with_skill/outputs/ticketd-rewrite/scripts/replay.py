#!/usr/bin/env python3
"""P7/execution: trace normalizer + divergence-aware differ (the L3 comparator).

Traces are JSONL: one JSON object per line, e.g.
  {"id": "auth-reset-001", "request": {...},
   "response": {"status": 200, "headers": {...}, "body": {...}}, "state": {...}}

Subcommands:
  normalize --rules diff-rules.yaml --in traces.jsonl [--out normalized.jsonl]
  diff --rules diff-rules.yaml [--divergences expected-divergences.yaml]
       --legacy legacy.jsonl --modern modern.jsonl [--out report.json]

diff exit code: 0 all pass, 1 failures. Expected divergences pass ONLY when they diverge
as specified; any unlisted divergence is a failure. Stdlib only (bundled mini-YAML reader).
"""
import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

# --------------------------- mini-YAML (restricted subset) ---------------------------
def load_yaml(path):
    """Parse the restricted YAML subset used by diff-rules / expected-divergences:
    nested dicts, lists ('- ' items), scalars, inline [a, b] lists. Falls back to
    json.loads for .json files. Not a general YAML parser — keep those files simple."""
    text = Path(path).read_text()
    if str(path).endswith(".json"):
        return json.loads(text)
    lines = [l for l in text.splitlines()
             if l.strip() and not l.strip().startswith("#")]
    # strip inline comments (naive: ' #' outside quotes)
    lines = [re.sub(r'\s+#(?![^"\']*["\']).*$', "", l) for l in lines]
    pos = [0]

    def scalar(s):
        s = s.strip().strip('"\'')
        if s.startswith("[") and s.endswith("]"):
            return [scalar(x) for x in s[1:-1].split(",") if x.strip()]
        for conv in (int, float):
            try:
                return conv(s)
            except ValueError:
                pass
        return {"true": True, "false": False, "null": None, "~": None}.get(s.lower(), s)

    def indent(l):
        return len(l) - len(l.lstrip())

    def parse_block(min_indent):
        if pos[0] >= len(lines):
            return None
        line = lines[pos[0]]
        if indent(line) < min_indent:
            return None
        if line.lstrip().startswith("- "):
            return parse_list(indent(line))
        return parse_dict(indent(line))

    def parse_list(ind):
        items = []
        while pos[0] < len(lines):
            line = lines[pos[0]]
            if indent(line) != ind or not line.lstrip().startswith("- "):
                break
            content = line.lstrip()[2:]
            pos[0] += 1
            if ":" in content:  # list of dicts: first pair inline, rest indented deeper
                k, _, v = content.partition(":")
                d = {k.strip(): scalar(v) if v.strip() else parse_block(ind + 2)}
                nxt = parse_dict(ind + 2, seed=d)
                items.append(nxt)
            else:
                items.append(scalar(content))
        return items

    def parse_dict(ind, seed=None):
        d = seed if seed is not None else {}
        while pos[0] < len(lines):
            line = lines[pos[0]]
            if indent(line) != ind or line.lstrip().startswith("- "):
                break
            k, _, v = line.lstrip().partition(":")
            pos[0] += 1
            d[k.strip()] = scalar(v) if v.strip() else parse_block(ind + 1)
        return d

    return parse_block(0) or {}


# --------------------------------- normalization ---------------------------------
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}|^\d{9,13}$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def path_matches(rule_path, keypath):
    """rule '$.**.updated_at' or '$.items' vs keypath tuple like ('body','items',3,'id')."""
    parts = rule_path.lstrip("$").strip(".").split(".")
    keys = [str(k) for k in keypath if not isinstance(k, int)]
    if parts and parts[0] == "**":
        return bool(keys) and keys[-1] == parts[-1]
    return keys == parts


def apply_rule(value, rule):
    rule = str(rule)
    if rule == "timestamp":
        return "<TS>" if isinstance(value, (int, float)) or (
            isinstance(value, str) and TS_RE.match(value)) else value
    if rule == "uuid":
        return "<UUID>" if isinstance(value, str) and UUID_RE.match(value) else value
    if rule == "drop":
        return "<DROPPED>"
    if rule.startswith("sort_by:"):
        key = rule.split(":", 1)[1]
        if isinstance(value, list):
            return sorted(value, key=lambda x: str(x.get(key)) if isinstance(x, dict) else str(x))
        return value
    return value


def normalize_obj(obj, rules, keypath=()):
    for r in rules.get("normalize", []) or []:
        if "path" in r and path_matches(r["path"], keypath):
            obj = apply_rule(obj, r["rule"])
    if isinstance(obj, dict):
        return {k: normalize_obj(v, rules, keypath + (k,)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_obj(v, rules, keypath + (i,)) for i, v in enumerate(obj)]
    return obj


def normalize_trace(trace, rules):
    t = normalize_obj(trace, rules)
    headers = (t.get("response") or {}).get("headers")
    if isinstance(headers, dict):
        drop = {h.lower() for h in rules.get("ignore_headers", []) or []}
        for r in rules.get("normalize", []) or []:
            if "header" in r and str(r.get("rule")) == "drop":
                drop.add(r["header"].lower())
        t["response"]["headers"] = {k: v for k, v in headers.items() if k.lower() not in drop}
    sd = rules.get("state_diff", {}) or {}
    state = t.get("state")
    if isinstance(state, dict) and isinstance(state.get("db_dump"), dict):
        cfg = sd.get("db_dump", {}) or {}
        for tbl in cfg.get("exclude_tables", []) or []:
            state["db_dump"].pop(tbl, None)
        for tbl, cols in (cfg.get("exclude_columns", {}) or {}).items():
            rows = state["db_dump"].get(tbl)
            if isinstance(rows, list):
                for row in rows:
                    for c in cols:
                        if isinstance(row, dict):
                            row.pop(c, None)
    return t


# ------------------------------------ diffing ------------------------------------
def get_field(trace, dotted):
    """Fetch '$.email_dispatch.mode' from the trace (searched in response.body, then root)."""
    parts = dotted.lstrip("$").strip(".").split(".")
    for base in ((trace.get("response") or {}).get("body"), trace):
        cur = base
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return None


def deep_diff(a, b, path="$"):
    if type(a) is not type(b):
        return [{"path": path, "legacy": a, "modern": b}]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += deep_diff(a.get(k), b.get(k), f"{path}.{k}")
        return out
    if isinstance(a, list):
        out = []
        if len(a) != len(b):
            out.append({"path": f"{path}.length", "legacy": len(a), "modern": len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            out += deep_diff(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [{"path": path, "legacy": a, "modern": b}]


def load_traces(path):
    out = {}
    for i, line in enumerate(Path(path).open()):
        line = line.strip()
        if not line:
            continue
        t = json.loads(line)
        out[t.get("id", f"line-{i}")] = t
    return out


def cmd_diff(args):
    rules = load_yaml(args.rules) if args.rules else {}
    divergences = load_yaml(args.divergences) if args.divergences else []
    legacy, modern = load_traces(args.legacy), load_traces(args.modern)
    results = []
    for tid in sorted(set(legacy) | set(modern)):
        if tid not in modern or tid not in legacy:
            results.append({"id": tid, "verdict": "fail",
                            "reason": f"missing on {'modern' if tid not in modern else 'legacy'} side"})
            continue
        ln = normalize_trace(json.loads(json.dumps(legacy[tid])), rules)
        mn = normalize_trace(json.loads(json.dumps(modern[tid])), rules)
        diffs = deep_diff(ln, mn)
        applicable = [d for d in divergences
                      if fnmatch.fnmatch(tid, d.get("match", {}).get("trace_pattern", ""))]
        explained, violations = [], []
        for d in applicable:
            field = d["match"]["field"]
            lv, mv = get_field(ln, field), get_field(mn, field)
            if lv == d.get("legacy") and mv == d.get("expected"):
                explained.append({"id": d.get("id"), "field": field, "status": "diverged as specified"})
                fieldtail = field.lstrip("$").strip(".").split(".")[-1]
                diffs = [x for x in diffs if not x["path"].endswith(fieldtail)]
            elif mv is not None and mv != d.get("expected"):
                violations.append({"id": d.get("id"), "field": field,
                                   "expected": d.get("expected"), "got": mv})
        verdict = "pass" if not diffs and not violations else "fail"
        results.append({"id": tid, "verdict": verdict, "unexpected_diffs": diffs,
                        "divergence_violations": violations, "expected_divergences": explained})
    passed = sum(1 for r in results if r["verdict"] == "pass")
    report = {"total": len(results), "passed": passed, "failed": len(results) - passed,
              "results": results}
    out = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(out + "\n")
    print(out if not args.out else
          f"{passed}/{len(results)} traces pass → {args.out}")
    sys.exit(0 if passed == len(results) else 1)


def cmd_normalize(args):
    rules = load_yaml(args.rules) if args.rules else {}
    lines = []
    for tid, t in load_traces(args.infile).items():
        lines.append(json.dumps(normalize_trace(t, rules), sort_keys=True))
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"{len(lines)} traces normalized → {args.out}")
    else:
        sys.stdout.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("normalize")
    n.add_argument("--rules")
    n.add_argument("--in", dest="infile", required=True)
    n.add_argument("--out")
    d = sub.add_parser("diff")
    d.add_argument("--rules")
    d.add_argument("--divergences")
    d.add_argument("--legacy", required=True)
    d.add_argument("--modern", required=True)
    d.add_argument("--out")
    args = ap.parse_args()
    (cmd_diff if args.cmd == "diff" else cmd_normalize)(args)


if __name__ == "__main__":
    main()
