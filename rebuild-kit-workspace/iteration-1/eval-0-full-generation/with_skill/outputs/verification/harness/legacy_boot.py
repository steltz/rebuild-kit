#!/usr/bin/env python3
"""Boot the pinned legacy app for the twin-boot harness.

- Substitutes smtplib.SMTP with a capture sink writing JSON lines
  ({"from","to","body"}) to $OUTBOX (mail-message.schema.json shape). The send stays
  synchronous inside the request — exactly legacy's mode — the sink only removes the
  network dependency on smtp.internal.
- Runs from a work dir containing db/ticketd.sqlite3 (DB_PATH is CWD-relative,
  ticketd/app/server.py:14). PYTHONPATH must include the legacy tree root.

Usage: legacy_boot.py --port 5001 --outbox path/to/outbox.jsonl
"""
import argparse
import json
import smtplib


class _SinkSMTP:
    outbox_path = None

    def __init__(self, host, port=25, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def sendmail(self, from_addr, to_addrs, msg):
        with open(self.outbox_path, "a") as f:
            f.write(json.dumps({"from": from_addr, "to": list(to_addrs),
                                "body": msg}) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--outbox", required=True)
    args = ap.parse_args()

    _SinkSMTP.outbox_path = args.outbox
    open(args.outbox, "a").close()
    smtplib.SMTP = _SinkSMTP  # patch BEFORE the app module binds it

    from app.server import app  # noqa: E402  (legacy import, read-only)
    app.run(port=args.port)


if __name__ == "__main__":
    main()
