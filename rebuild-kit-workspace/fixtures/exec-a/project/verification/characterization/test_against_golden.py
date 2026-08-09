"""L2 characterization tests: fast, local, run against a MODERN instance you already have
running (unlike L3's diff-run.sh, this does not boot anything itself). Each captured T2 golden
trace under verification/replay/traces/legacy/*.jsonl becomes one parametrized test case: replay
its recorded request against modern, assert response status + normalized body match.

This intentionally reuses verification/harness/replay.py's normalize/diff logic rather than
reimplementing field-by-field assertions per route -- one source of truth for "what counts as a
match" between L2 (this file) and L3 (diff-run.sh). State/DB diffing is L3-only (it needs a
fresh, seeded, hermetic boot per suite); L2 checks the HTTP contract only.

Usage:
    MODERN_BASE_URL=http://127.0.0.1:8000 pytest verification/characterization/ -v

Before modern/ exists (pre-Milestone-0), every test in here is expected to be SKIPPED, not
failed -- see the fixture below. That's a deliberate signal, not a gap: root CLAUDE.md's
executor loop runs L1+L2 locally per WO, and WO-001 is the first WO that gives these anything
to hit.
"""
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "verification" / "harness"))
from replay import load_yaml, normalize_trace, deep_diff, get_field  # vendored, see harness/replay.py

GOLDEN_DIR = ROOT / "verification" / "replay" / "traces" / "legacy"
DIFF_RULES = load_yaml(ROOT / "verification" / "replay" / "diff-rules.yaml")
DIVERGENCES = load_yaml(ROOT / "verification" / "replay" / "expected-divergences.yaml")
MODERN_BASE_URL = os.environ.get("MODERN_BASE_URL")


def _load_all_goldens():
    cases = []
    for f in sorted(GOLDEN_DIR.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                cases.append(json.loads(line))
    return cases


GOLDEN_CASES = _load_all_goldens()


@pytest.fixture(scope="session", autouse=True)
def require_modern_base_url():
    if not MODERN_BASE_URL:
        pytest.skip(
            "MODERN_BASE_URL not set -- expected before Milestone 0 exists. Set it to a "
            "running modern/ instance's base URL to exercise these characterization tests "
            "(see verification/harness/README.md and root CLAUDE.md's executor loop)."
        )


def _send(base_url, req):
    url = base_url.rstrip("/") + req["path"]
    body = req.get("body")
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(req.get("headers") or {})
    if data is not None:
        headers.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, data=data, method=req.get("method", "GET"), headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            status, raw = resp.status, resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
    if "application/json" in ctype:
        try:
            parsed = json.loads(raw.decode()) if raw else {}
        except json.JSONDecodeError:
            parsed = raw.decode(errors="replace")
    else:
        parsed = raw.decode(errors="replace")
    return {"status": status, "headers": {"Content-Type": ctype}, "body": parsed}


@pytest.mark.parametrize("golden", GOLDEN_CASES, ids=lambda g: g["id"])
def test_response_matches_golden(golden):
    """Replays golden['request'] against modern and diffs the RESPONSE only (not state --
    that requires the hermetic per-suite boot L3 provides) against the legacy golden, through
    the same normalize/diff-rules pipeline the L3 harness uses -- INCLUDING
    expected-divergences.yaml, so REPAIR-tagged behaviors (PB-001 async dispatch, PB-002 token
    mechanism) are asserted against their RULED target, not against old legacy behavior. A WO
    that changes response-body-visible behavior without a matching ED entry here is exactly
    the "unsanctioned drift" case schema.md's fidelity taxonomy exists to catch -- this test
    failing is often correct, not a bug in the test.
    """
    actual = {"id": golden["id"], "request": golden["request"],
              "response": _send(MODERN_BASE_URL, golden["request"])}
    expected = {"id": golden["id"], "request": golden["request"], "response": golden["response"]}
    ln = normalize_trace(json.loads(json.dumps(expected)), DIFF_RULES)
    mn = normalize_trace(json.loads(json.dumps(actual)), DIFF_RULES)
    diffs = deep_diff(ln.get("response"), mn.get("response"), path="$.response")

    applicable = [d for d in DIVERGENCES
                  if fnmatch.fnmatch(golden["id"], d.get("match", {}).get("trace_pattern", ""))]
    violations = []
    for d in applicable:
        field = d["match"]["field"]
        lv, mv = get_field(ln, field), get_field(mn, field)
        if lv == d.get("legacy") and mv == d.get("expected"):
            fieldtail = field.lstrip("$").strip(".").split(".")[-1]
            diffs = [x for x in diffs if not x["path"].endswith(fieldtail)]
        elif mv is not None and mv != d.get("expected"):
            violations.append({"id": d.get("id"), "field": field,
                               "expected": d.get("expected"), "got": mv})

    assert not diffs and not violations, (
        f"{golden['id']}: modern response diverges from legacy golden (after diff-rules "
        f"normalization + expected-divergences) with no ratified explanation:\n"
        f"unexpected_diffs={json.dumps(diffs, indent=2)}\n"
        f"divergence_violations={json.dumps(violations, indent=2)}\n"
        f"If this divergence is intentional (a REPAIR target), it needs a human-ratified entry "
        f"in verification/replay/expected-divergences.yaml -- see schema.md."
    )
