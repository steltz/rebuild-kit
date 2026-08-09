#!/usr/bin/env python3
"""Direct regression test for the June 2026 SMTP outage that triggered this
rewrite. Legacy ticketd called SMTP synchronously inside POST
/api/tickets/<id>/close with a 30s timeout -- when SMTP was down, close
requests piled up and took the app down with it for 40 minutes.

This script hits POST /api/tickets/<id>/close repeatedly against a RUNNING
instance of the new API and asserts request latency stays low and bounded,
REGARDLESS of whether SMTP is reachable. It does not itself take SMTP down
-- point the app under test at an already-unreachable SMTP target before
running this (see usage below), so this script only needs to measure, not
orchestrate infrastructure.

Usage:
    # 1. Start the new API + worker with SMTP_HOST pointed at an
    #    unreachable address. 203.0.113.0/24 is TEST-NET-3 (RFC 5737),
    #    guaranteed non-routable -- safe to use, will never accidentally
    #    reach a real mail server.
    SMTP_HOST=203.0.113.1 SMTP_PORT=25 uvicorn app.main:app --port 8000 &
    SMTP_HOST=203.0.113.1 SMTP_PORT=25 python -m app.worker &

    # 2. Run this script against it
    python smtp_outage_test.py --base-url http://localhost:8000 --requests 30 --max-p99-ms 500

Exits non-zero (and prints the failure) if the p99 close-request latency
exceeds --max-p99-ms, or if any close request errors out because of SMTP
(it must not -- the request path should never touch SMTP at all, per
DESIGN-async-notifications.md).
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def _request(base_url: str, method: str, path: str, body: dict | None = None) -> tuple[int, float, dict | None]:
    url = base_url.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    start = time.monotonic()
    parsed = None
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
    elapsed = time.monotonic() - start
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, NameError):
        parsed = None
    return status, elapsed, parsed


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, int(round((p / 100) * (len(values) - 1))))
    return values[idx]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=30,
                         help="number of tickets to create-then-close")
    parser.add_argument("--max-p99-ms", type=float, default=500.0,
                         help="fail if p99 close latency exceeds this many ms "
                              "(legacy's failure mode was up to 30000ms per request)")
    args = parser.parse_args()

    close_latencies_ms = []
    failures = []

    for i in range(args.requests):
        status, _, created = _request(args.base_url, "POST", "/api/tickets",
                                       {"title": f"outage-test-{i}-{time.time()}"})
        if status != 201 or not created or "id" not in created:
            failures.append(f"ticket creation #{i} failed with status {status}")
            continue
        ticket_id = created["id"]

        status, elapsed, _ = _request(args.base_url, "POST", f"/api/tickets/{ticket_id}/close")
        close_latencies_ms.append(elapsed * 1000)
        if status != 200:
            failures.append(f"close #{i} (ticket {ticket_id}) failed with status {status}")

    p50 = percentile(close_latencies_ms, 50)
    p99 = percentile(close_latencies_ms, 99)
    worst = max(close_latencies_ms) if close_latencies_ms else 0.0

    print(f"close requests: {len(close_latencies_ms)}, failures: {len(failures)}")
    print(f"latency (ms): p50={p50:.1f} p99={p99:.1f} worst={worst:.1f}")

    ok = True
    if failures:
        ok = False
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")

    if p99 > args.max_p99_ms:
        ok = False
        print(f"\nFAIL: p99 close latency {p99:.1f}ms exceeds threshold {args.max_p99_ms}ms.")
        print("If SMTP is genuinely unreachable in this test run and latency is")
        print("elevated, the close endpoint is still calling SMTP synchronously")
        print("somewhere -- this is the exact bug this rewrite exists to fix.")
    else:
        print(f"\nPASS: close-request latency stayed under {args.max_p99_ms}ms "
              f"regardless of SMTP reachability.")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
