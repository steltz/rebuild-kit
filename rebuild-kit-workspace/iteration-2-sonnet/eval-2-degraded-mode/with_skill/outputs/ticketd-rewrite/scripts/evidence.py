#!/usr/bin/env python3
"""P2 runtime-evidence ingestion: parse access logs (Common/Combined Log Format or
JSON-lines), scrub PII at intake, join against the P1 route map, and emit
usage-weights.json, perf-envelopes.json, and the zero-traffic report.

Usage: evidence.py --logs FILE [FILE...] [--root ROOT] [--window-days N]
JSON-lines recognized keys: path|url, method, status, duration_ms|response_time|latency_ms.
Combined-with-timing: a trailing float field is read as request seconds (nginx $request_time).
"""
import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rk_common import die, find_root, scrub

CLF = re.compile(r'\S+ \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \S+'
                 r'(?: "[^"]*" "[^"]*")?(?: ([\d.]+))?\s*$')


def route_matcher(routes):
    """Compile route patterns (:id, <id>, {id} styles) into regexes, longest first."""
    compiled = []
    for r in routes:
        pat = re.sub(r"<[^>]+>|\{[^}]+\}|:[A-Za-z_]+", r"[^/]+", r["path"].rstrip("/") or "/")
        try:
            compiled.append((r, re.compile("^" + pat + "/?$")))
        except re.error:
            pass
    compiled.sort(key=lambda t: -len(t[0]["path"]))

    def match(method, path):
        path = path.split("?")[0]
        for r, rx in compiled:
            if rx.match(path) and (r["method"] in ("USE", "ALL") or r["method"] == method):
                return f"{r['method']} {r['path']}"
        return None
    return match


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            return None
        path = d.get("path") or d.get("url")
        if not path:
            return None
        dur = d.get("duration_ms") or d.get("response_time") or d.get("latency_ms")
        return {"method": str(d.get("method", "GET")).upper(), "path": path,
                "status": int(d.get("status", 0)), "ms": float(dur) if dur is not None else None}
    m = CLF.match(line)
    if m:
        ms = float(m.group(4)) * 1000 if m.group(4) else None
        return {"method": m.group(1).upper(), "path": m.group(2),
                "status": int(m.group(3)), "ms": ms}
    return None


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, round(p / 100 * (len(sorted_vals) - 1))))
    return round(sorted_vals[idx], 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", nargs="+", required=True)
    ap.add_argument("--root")
    ap.add_argument("--window-days", type=int, help="observation window, recorded in outputs")
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else find_root()
    if not root:
        die("no rebuild.json found — run scaffold.py first")
    inv_path = root / "inventory.json"
    if not inv_path.exists():
        die("inventory.json missing — run inventory.py first (P1); the route map is the join key")
    routes = json.loads(inv_path.read_text())["routes"]
    match = route_matcher(routes)

    hits = defaultdict(int)
    durs = defaultdict(list)
    statuses = defaultdict(lambda: defaultdict(int))
    unmatched, total, parsed = defaultdict(int), 0, 0
    for logfile in args.logs:
        for raw in Path(logfile).open(errors="replace"):
            total += 1
            rec = parse_line(scrub(raw))
            if not rec:
                continue
            parsed += 1
            key = match(rec["method"], rec["path"])
            if key is None:
                unmatched[f"{rec['method']} {rec['path'].split('?')[0]}"] += 1
                continue
            hits[key] += 1
            statuses[key][str(rec["status"])[0] + "xx"] += 1
            if rec["ms"] is not None:
                durs[key].append(rec["ms"])

    if parsed == 0:
        die(f"parsed 0 of {total} lines — unsupported log format? (CLF/combined or JSON-lines)")

    matched_total = sum(hits.values())
    weights = {k: round(v / matched_total, 5) for k, v in
               sorted(hits.items(), key=lambda kv: -kv[1])}
    (root / "usage-weights.json").write_text(json.dumps({
        "source": "access-logs", "window_days": args.window_days,
        "lines_total": total, "lines_parsed": parsed, "lines_matched": matched_total,
        "weights": weights,
        "status_mix": {k: dict(v) for k, v in statuses.items()},
        "unmatched_top": dict(sorted(unmatched.items(), key=lambda kv: -kv[1])[:20]),
    }, indent=2) + "\n")

    envelopes = {}
    for k, vals in durs.items():
        vals.sort()
        envelopes[k] = {"n": len(vals), "p50_ms": pct(vals, 50), "p95_ms": pct(vals, 95),
                        "p99_ms": pct(vals, 99)}
    (root / "perf-envelopes.json").write_text(json.dumps({
        "source": "access-logs", "note": "NFR floors: the rewrite must not regress these",
        "envelopes": envelopes or None,
        "unavailable_reason": None if envelopes else "log format carried no timing field",
    }, indent=2) + "\n")

    zero = [f"{r['method']} {r['path']}" for r in routes
            if f"{r['method']} {r['path']}" not in hits]
    lines = ["# Zero-Traffic Report", "",
             f"Observed window: {args.window_days or 'UNKNOWN'} days · "
             f"{matched_total} matched requests", "",
             "Routes in code with no observed traffic. Zero-traffic ≠ dead: check window "
             "coverage (cron/seasonal), admin paths, webhook receivers. Promote to "
             "do-not-port.md only with corroborating static evidence.", ""]
    lines += [f"- `{z}` — confidence: low, corroboration: <FILL>" for z in zero] or ["(none)"]
    (root / "zero-traffic.md").write_text("\n".join(lines) + "\n")

    print(json.dumps({"parsed": parsed, "matched": matched_total,
                      "routes_with_traffic": len(hits), "zero_traffic_routes": len(zero),
                      "perf_envelopes": bool(envelopes),
                      "unmatched_distinct": len(unmatched)}, indent=2))
    print("\nNext: set rebuild.json evidence.runtime_ingestion=active; review unmatched_top "
          "(dynamic routes the P1 map missed?); judge zero-traffic entries before any "
          "do-not-port promotion.")


if __name__ == "__main__":
    main()
