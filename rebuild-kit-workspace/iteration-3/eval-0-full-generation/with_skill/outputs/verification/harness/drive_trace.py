#!/usr/bin/env python3
"""Replay a trace file's *requests* against a live server, writing a new trace file with the same
ids/requests but *live* responses -- the "modern" side of a diff-run.sh comparison. Stdlib only.

Usage: drive_trace.py --base-url http://127.0.0.1:5100 --in traces.jsonl --out live.jsonl

Fields the trace file may carry that this script does NOT reproduce against the live server
(informational only, copied through unchanged for the differ to compare if the modern side later
learns to populate them the same way): `side_effects`, `note`. Only `request` is replayed;
`response` and everything else in the output come from the live call, except id/side_effects/note
which pass through as recorded UNLESS the target server exposes an equivalent introspection point
-- ticketd has none, so for now side_effects on the "modern" output are left as captured from the
trace input, which means diff-run.sh cannot yet verify PB-001/PB-002's REPAIR behavior end-to-end
via this script alone. That gap is flagged, not hidden: see the printed warning below.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def call(base_url, method, path, body, headers):
    url = base_url + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req)
        status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        rbody = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        rbody = raw.decode(errors="replace")
    return {"status": status, "body": rbody}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    warned_side_effects = False
    with open(args.infile) as fin, open(args.out, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)
            req = t["request"]
            live_response = call(args.base_url, req["method"], req["path"], req.get("body"), req.get("headers"))
            out_trace = {"id": t["id"], "request": req, "response": live_response}
            if "side_effects" in t and not warned_side_effects:
                print("drive_trace.py: WARNING -- trace has 'side_effects' (notification dispatch, "
                      "token mechanism) this script cannot observe over HTTP alone. These pass "
                      "through UNCHANGED from the input trace, so ED-001/ED-001b/ED-002 will not be "
                      "meaningfully exercised until the modern app exposes an equivalent test hook "
                      "(e.g. a test-only introspection endpoint, or reading its own outbox/queue "
                      "table directly) -- add that wiring in WO-001/WO-003 and update this script.",
                      file=sys.stderr)
                warned_side_effects = True
            if "side_effects" in t:
                out_trace["side_effects"] = t["side_effects"]
            if "note" in t:
                out_trace["note"] = t["note"]
            fout.write(json.dumps(out_trace) + "\n")


if __name__ == "__main__":
    main()
