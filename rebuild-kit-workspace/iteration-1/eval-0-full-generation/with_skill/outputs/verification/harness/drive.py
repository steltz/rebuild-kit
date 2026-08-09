#!/usr/bin/env python3
"""T2 session driver: send an input set through a booted tree, record replay traces.

Input set: JSONL, one entry per line:
  {"id": "tickets-create-001",
   "request": {"method": "POST", "path": "/api/tickets",
               "headers": {...}?, "body": {...}? , "raw_body": "..."?},
   "extract": {"var": "tok1", "from": "outbox", "regex": "reset token: (.+)$"}?}

String values in request.body of the form "$name" are substituted from extracted vars.

Trace output (replay.py schema): one JSON object per line —
  {"id", "request", "response": {"status", "headers": {"content-type"}, "body":
      {"json": ...} | {"text": ...}},
   "state": {"db_dump": {...}, "email": {"mode", "messages": [{"to", "body_redacted"}]}?,
             "token_store": {"cleartext": bool}?}}

- state.db_dump comes from --state-cmd (a command printing the DB as JSON).
- state.email appears only when the request emitted mail (delta of --outbox file);
  mode is the runner's declared dispatch mode: legacy runner passes "sync" (mail leaves
  during the request — legacy_boot.py's sink is called in-request); the modern runner
  passes "queued" and MUST flush its dispatcher before drive.py samples the outbox
  (run-modern.sh contract). Token material in bodies is redacted to <TOKEN>.
- state.token_store.cleartext: for reset requests — whether the token string emailed to
  the user appears verbatim in the DB dump (observable PB-002 predicate; ED-002).
"""
import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request

TOKEN_RE = re.compile(r"(reset token: ).+$", re.M)


def http(base, req, variables):
    url = base + req["path"]
    body = None
    headers = dict(req.get("headers") or {})
    if "raw_body" in req:
        body = req["raw_body"].encode()
        headers.setdefault("Content-Type", "application/json")
    elif "body" in req:
        sub = {k: (variables.get(v[1:], v) if isinstance(v, str) and v.startswith("$") else v)
               for k, v in req["body"].items()}
        body = json.dumps(sub).encode()
        headers.setdefault("Content-Type", "application/json")
    r = urllib.request.Request(url, data=body, method=req["method"], headers=headers)
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        status, ctype, payload = resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as e:
        status, ctype, payload = e.code, e.headers.get("Content-Type", ""), e.read()
    ctype = ctype.split(";")[0].strip()
    try:
        parsed = {"json": json.loads(payload)}
    except (ValueError, UnicodeDecodeError):
        parsed = {"text": payload.decode(errors="replace")}
    return {"status": status, "headers": {"content-type": ctype}, "body": parsed}


def read_outbox(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


def db_dump(cmd):
    return json.loads(subprocess.run(cmd, shell=True, check=True,
                                     capture_output=True, text=True).stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--outbox", required=True)
    ap.add_argument("--state-cmd", required=True)
    ap.add_argument("--email-mode", required=True, choices=["sync", "queued"])
    ap.add_argument("--settle-ms", type=int, default=0,
                    help="wait after each request before sampling outbox/state (modern queued mode)")
    args = ap.parse_args()

    variables, traces = {}, []
    entries = [json.loads(l) for l in open(args.input) if l.strip()]
    for e in entries:
        before = len(read_outbox(args.outbox))
        response = http(args.base_url, e["request"], variables)
        if args.settle_ms:
            time.sleep(args.settle_ms / 1000)
        outbox = read_outbox(args.outbox)
        new_mail = outbox[before:]
        dump = db_dump(args.state_cmd)
        state = {"db_dump": dump}
        if new_mail:
            state["email"] = {"mode": args.email_mode,
                              "messages": [{"to": m["to"],
                                            "body_redacted": TOKEN_RE.sub(r"\1<TOKEN>", m["body"])}
                                           for m in new_mail]}
        if e.get("extract"):
            m = re.search(e["extract"]["regex"], new_mail[-1]["body"]) if new_mail else None
            if m:
                variables[e["extract"]["var"]] = m.group(1)
        if e["id"].startswith("auth-reset-req") and new_mail:
            m = re.search(r"reset token: (.+)$", new_mail[-1]["body"], re.M)
            tok = m.group(1) if m else None
            stored = json.dumps(dump.get("reset_tokens", [])) + json.dumps(dump)
            state["token_store"] = {"cleartext": bool(tok) and tok in stored}
        req_rec = json.loads(json.dumps(e["request"]))
        traces.append({"id": e["id"], "request": req_rec, "response": response, "state": state})

    with open(args.out, "w") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")
    print(f"{len(traces)} traces -> {args.out}")


if __name__ == "__main__":
    main()
