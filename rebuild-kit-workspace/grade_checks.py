#!/usr/bin/env python3
"""Mechanical grading checks for rebuild-kit evals.

Usage: grade_checks.py --eval {0,1,2} --outputs DIR [--fixture DIR]
Prints JSON: {check_name: {"ok": bool|null, "evidence": str}}. ok=null means the check
could not be evaluated mechanically (grader judges from the artifacts instead — common
for baseline runs that used their own layout).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def find_workspace(outputs):
    """The rewrite root: a dir under outputs containing rebuild.json, else outputs itself."""
    for p in [outputs, *sorted(outputs.rglob("rebuild.json"))]:
        if (p / "rebuild.json").is_file() if p.is_dir() else True:
            return p if p.is_dir() else p.parent
    return None


def grep_tree(base, pattern, exts=(".md", ".json", ".yaml", ".yml", ".txt")):
    rx = re.compile(pattern, re.IGNORECASE)
    hits = []
    for p in base.rglob("*"):
        if p.suffix in exts and p.is_file() and ".git" not in p.parts:
            try:
                for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{p.relative_to(base)}:{i}: {line.strip()[:120]}")
            except OSError:
                pass
    return hits


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def check_eval0(outputs, checks):
    ws = find_workspace(outputs)
    legacy = None
    if ws and (ws / "rebuild.json").exists():
        cfg = json.loads((ws / "rebuild.json").read_text())
        legacy = ws / cfg.get("layout", {}).get("legacy_dir", "ticketd")
        code, head = run(["git", "-C", str(legacy), "rev-parse", "HEAD"])
        pin_ok = code == 0 and cfg.get("legacy_ref", "")[:12] == head.strip()[:12]
        checks["layout-and-pin"] = {"ok": pin_ok,
                                    "evidence": f"rebuild.json legacy_ref={cfg.get('legacy_ref', '')[:12]} vs HEAD={head.strip()[:12] if code == 0 else 'n/a'}"}
    else:
        checks["layout-and-pin"] = {"ok": None, "evidence": "no rebuild.json found — judge manually"}
        legacy = next(iter(outputs.rglob("ticketd")), None)

    if legacy and legacy.is_dir():
        target = legacy / "README.md"
        try:
            with open(target, "a"):
                pass
            writable = True
        except (PermissionError, OSError):
            writable = False
        hook = bool(list((ws or outputs).rglob("*pre-commit*"))) if ws else False
        gitlink = False
        if ws:
            code, out = run(["git", "-C", str(ws), "ls-files", "-s"], cwd=None)
            gitlink = any(l.startswith("160000") for l in out.splitlines())
        checks["legacy-protected"] = {
            "ok": (not writable) or hook or gitlink,
            "evidence": f"writable={writable}, pre-commit-hook={hook}, gitlink-pin={gitlink}"}
    else:
        checks["legacy-protected"] = {"ok": None, "evidence": "legacy tree not located"}

    base = ws or outputs
    facts = {"sync-email": r"synchronous|sync.*(email|mail)|smtp.*(block|outage)",
             "md5": r"md5", "slug": r"slug.*colli|colli.*slug", "no-ui": r"ui change|no ui|ui.*out of scope"}
    found = {k: bool(grep_tree(base, v)) for k, v in facts.items()}
    pbids = grep_tree(base, r"\bPB-\d+")
    undis = grep_tree(base, r"UNDISPOSITIONED")
    checks["problem-brief"] = {"ok": all(found.values()) and bool(pbids),
                               "evidence": f"facts found={found}, PB-ids={len(pbids)}, undispositioned-mentions={len(undis)}"}

    tags = {t: len(grep_tree(base, rf"\b{t}\b")) for t in ("FIXED", "REPAIR", "FREE", "ASK")}
    checks["fidelity-tags"] = {"ok": all(tags[t] > 0 for t in ("FIXED", "REPAIR", "ASK")) or None,
                               "evidence": f"tag mentions={tags} (citation resolution: grader verifies samples)"}

    quirk = grep_tree(base, r"(200|empty).*(missing|not.?found|nonexistent).*ticket|missing.*ticket.*(200|empty)|never 404|not 404")
    checks["missing-ticket-quirk"] = {"ok": bool(quirk), "evidence": quirk[:3] or ["not found"]}

    div = grep_tree(base, r"expected.divergen|ED-\d+")
    sync_repair = grep_tree(base, r"REPAIR.*(mail|email|smtp|notif|outbox|queue|async)|(mail|email|smtp|notif).*REPAIR")
    checks["sync-email-sanctioned"] = {"ok": bool(div) and bool(sync_repair),
                                       "evidence": (sync_repair[:2] + div[:2]) or ["not found"]}

    slug_ask = grep_tree(base, r"(OQ-\d+|open.question|ASK).*slug|slug.*(OQ-\d+|open.question|ASK)")
    slug_decided = grep_tree(base, r"slug.*(REPAIR|FIXED.*suffix|unique.*suffix)")
    checks["slug-is-open-question"] = {"ok": bool(slug_ask) and not bool(slug_decided),
                                       "evidence": f"ask-refs={len(slug_ask)}, decided-refs={slug_decided[:2]}"}

    uw = next(iter(base.rglob("usage-weights.json")), None)
    if uw:
        w = json.loads(uw.read_text()).get("weights", {})
        top = next(iter(w), None)
        checks["usage-weights"] = {"ok": top is not None and "GET /api/tickets" in top,
                                   "evidence": f"top={top}"}
    else:
        hits = grep_tree(base, r"usage.?weight|traffic share|request share")
        checks["usage-weights"] = {"ok": None if hits else False,
                                   "evidence": f"no usage-weights.json; textual mentions={len(hits)}"}
    zt = grep_tree(base, r"internal/export/csv")
    checks["zero-traffic-flagged"] = {"ok": bool(zt), "evidence": zt[:3] or ["export route never mentioned"]}

    ledger = next(iter(base.rglob("ledger.json")), None)
    skel = grep_tree(base, r"walking skeleton|thin.*end.to.end|end.to.end slice")
    checks["backlog-ledger-m0"] = {"ok": bool(ledger) and bool(skel),
                                   "evidence": f"ledger={bool(ledger)}, walking-skeleton-refs={len(skel)}"}

    harness = {f: bool(list(base.rglob(f))) for f in
               ("diff-rules.yaml", "expected-divergences.yaml", "run-legacy.sh", "run-modern.sh")}
    checks["verification-harness"] = {"ok": all(harness.values()) or None if any(harness.values()) else False,
                                      "evidence": str(harness)}


def check_eval1(outputs, checks, fixture):
    ws = next(iter(outputs.rglob("rebuild.json")), None)
    ws = ws.parent if ws else outputs
    oq = ws / "docs" / "open-questions.md"
    if oq.exists():
        text = oq.read_text(errors="replace")
        block = re.search(r"## OQ-002.*?(?=\n## |\Z)", text, re.DOTALL)
        b = block.group(0) if block else ""
        checks["ruling-recorded"] = {
            "ok": bool(b) and "PENDING" not in b.split("ruling:")[-1][:40] and "Dana" in b
                  and ("suffix" in b or "unique" in b) and "readings" in b,
            "evidence": b[-300:] if b else "no OQ-002 block"}
    else:
        checks["ruling-recorded"] = {"ok": None, "evidence": "open-questions.md not at expected path"}

    wo2 = next(iter(ws.rglob("WO-002*.md")), None)
    if wo2:
        t = wo2.read_text(errors="replace")
        slug_seg = "\n".join(l for l in t.splitlines() if "slug" in l.lower() or "REPAIR" in l or "ASK" in l)
        checks["wo2-retagged"] = {"ok": "REPAIR" in t and not re.search(r"fidelity:\s*ASK", t),
                                  "evidence": slug_seg[:400]}
    else:
        checks["wo2-retagged"] = {"ok": None, "evidence": "WO-002 file not found"}

    div = next(iter(ws.rglob("expected-divergences.yaml")), None)
    if div:
        d = div.read_text(errors="replace")
        checks["divergence-added"] = {"ok": "slug" in d.lower() and "PB-003" in d,
                                      "evidence": d[-400:]}
    else:
        checks["divergence-added"] = {"ok": False, "evidence": "manifest missing"}

    led = ws / "ledger.json"
    if led.exists():
        L = json.loads(led.read_text())
        wo = next((w for w in L.get("work_orders", []) if w.get("id") == "WO-002"), {})
        checks["ledger-unblocked"] = {
            "ok": "OQ-002" not in wo.get("blocked_by_asks", []) and wo.get("status") != "awaiting_ruling",
            "evidence": json.dumps(wo)[:300]}
    else:
        checks["ledger-unblocked"] = {"ok": False, "evidence": "ledger.json missing"}

    brief = ws / "docs" / "problem-brief.md"
    if brief.exists():
        t = brief.read_text(errors="replace")
        m = re.search(r"### PB-003.*?(?=\n### |\n## |\Z)", t, re.DOTALL)
        b = m.group(0) if m else ""
        checks["pb3-dispositioned"] = {"ok": bool(b) and "UNDISPOSITIONED" not in b,
                                       "evidence": b[-200:] if b else "no PB-003"}
    else:
        checks["pb3-dispositioned"] = {"ok": None, "evidence": "problem-brief.md not found"}

    nomig = grep_tree(ws, r"(existing|old|stored).*(slug).*(unchanged|stay|keep|as.is|no migration)|no migration.*slug")
    checks["no-migration-preserved"] = {"ok": bool(nomig), "evidence": nomig[:3] or ["not stated"]}

    if fixture:
        surgical, ev = True, []
        for rel in ("docs/features/WO-001-reset-and-notify.md",):
            a, b = fixture / rel, ws / rel
            same = a.exists() and b.exists() and a.read_text() == b.read_text()
            surgical &= same
            ev.append(f"{rel}: {'unchanged' if same else 'CHANGED/MISSING'}")
        for key in ("legacy_ref",):
            fa = json.loads((fixture / "rebuild.json").read_text()).get(key)
            fb = json.loads((ws / "rebuild.json").read_text()).get(key) if (ws / "rebuild.json").exists() else None
            surgical &= fa == fb
            ev.append(f"rebuild.json {key}: {'unchanged' if fa == fb else 'CHANGED'}")
        checks["surgical-patch"] = {"ok": surgical, "evidence": "; ".join(ev)}

    dec = ws / "guide" / "decisions.md"
    if dec.exists():
        t = dec.read_text(errors="replace")
        ruled = re.search(r"Rulings.*OQ-002", t, re.DOTALL) and not re.search(
            r"Still open.*OQ-002", t, re.DOTALL)
        checks["guide-refreshed"] = {"ok": bool(ruled), "evidence": t[-400:]}
    else:
        checks["guide-refreshed"] = {"ok": False, "evidence": "guide/decisions.md missing"}


def check_eval2(outputs, checks):
    ws = next(iter(outputs.rglob("rebuild.json")), None)
    base = ws.parent if ws else outputs
    if ws:
        ev = json.loads(ws.read_text()).get("evidence", {})
        inactive = [k for k, v in ev.items() if v == "inactive"]
        checks["degraded-recorded"] = {
            "ok": {"runtime_ingestion", "data_census", "trace_capture_t1"} <= set(inactive),
            "evidence": json.dumps(ev)}
    else:
        hits = grep_tree(base, r"(no|without|missing|unavailable).*(log|traffic|git history|evidence)")
        checks["degraded-recorded"] = {"ok": None, "evidence": f"no rebuild.json; honesty mentions={len(hits)}"}

    perf = grep_tree(base, r"p9[59]|p50|latency.*\d+\s*ms|\d+\s*ms.*latency")
    observed = grep_tree(base, r"\d+(\.\d+)?%.*(of )?(traffic|requests)|traffic.*\d+(\.\d+)?%")
    fab = [h for h in perf + observed if not re.search(
        r"unavailable|absent|proxy|assum|estimat|unknown|n/a|not measured|no data|placeholder|TBD|target|goal|budget|floor|NFR|SLO|must|should", h, re.IGNORECASE)]
    checks["no-fabricated-evidence"] = {"ok": not fab, "evidence": fab[:5] or ["no unlabeled perf/traffic numbers found"]}

    uw = next(iter(base.rglob("usage-weights.json")), None)
    if uw:
        src = json.loads(uw.read_text()).get("source", "")
        checks["weights-labeled-proxy"] = {"ok": "proxy" in src or "static" in src or "assum" in src,
                                           "evidence": f"source={src}"}
    else:
        lab = grep_tree(base, r"(static|proxy|assumption).*(weight|priorit)|weight.*(proxy|assum)")
        checks["weights-labeled-proxy"] = {"ok": None, "evidence": f"no usage-weights.json; labeled mentions={len(lab)}"}

    tags = {t: len(grep_tree(base, rf"\b{t}\b")) for t in ("FIXED", "REPAIR", "ASK")}
    cites = grep_tree(base, r"ticketd/app/(server|util|notify)\.py:\d+")
    checks["specs-code-only"] = {"ok": all(v > 0 for v in tags.values()) and len(cites) >= 3,
                                 "evidence": f"tags={tags}, resolving-citation-mentions={len(cites)}"}

    pb = grep_tree(base, r"\bPB-\d+")
    oq_gaps = grep_tree(base, r"open intake|intake gap|could not (be )?ask|unreachable|open.question")
    checks["brief-and-gaps"] = {"ok": bool(pb) and bool(oq_gaps),
                                "evidence": f"PB-refs={len(pb)}, gap-recordings={len(oq_gaps)}"}

    census = list(base.rglob("census-queries.sql")) or grep_tree(base, r"census.*quer|SELECT COUNT\(\*\)")
    checks["census-shipped"] = {"ok": bool(census), "evidence": str(census[:3]) or "none"}

    tier = grep_tree(base, r"\bT1\b.*(unavailable|inactive|absent|none)|provisional|T3.*(flag|provisional)|no production traffic")
    checks["tier-honest"] = {"ok": bool(tier), "evidence": tier[:3] or ["no tier honesty found"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=int, required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--fixture")
    args = ap.parse_args()
    outputs = Path(args.outputs).resolve()
    checks = {}
    fn = {0: lambda: check_eval0(outputs, checks),
          1: lambda: check_eval1(outputs, checks, Path(args.fixture).resolve() if args.fixture else None),
          2: lambda: check_eval2(outputs, checks)}[args.eval]
    fn()
    print(json.dumps(checks, indent=2, default=str))


if __name__ == "__main__":
    main()
