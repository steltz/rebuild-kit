"""Replay-harness-only SMTP stub. NOT part of legacy/ — legacy stays unmodified and read-only.

legacy/app/notify.py looks up `smtplib.SMTP` as an attribute at call time (inside a `with
smtplib.SMTP(...) as s:` block), not at import time, so replacing the attribute on the `smtplib`
module before any request handler runs is sufficient — no legacy source file is touched.

smtp.internal does not exist in this sandbox (and wouldn't, in any twin-boot environment that
isn't the original production network), so real legacy code exercising send_mail() would hang
until its 30s timeout and then raise. Stubbing it is a harness necessity, not a spec change: real
outbound email behavior (PB-001's synchronous-blocking problem) is evidenced from source
(app/notify.py:1 docstring, the two call sites) and from this stub's own recorded call log, which
the diff-rules state_diff can compare — did modern/ send equivalent mail, in equivalent (async)
fashion.
"""
import json
import os
import time

SENT_LOG = os.environ.get("TICKETD_SMTP_LOG", "sent_mail.jsonl")


class _FakeSMTPInstance:
    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sendmail(self, from_addr, to_addrs, msg):
        record = {
            "ts": time.time(),
            "from": from_addr,
            "to": to_addrs,
            "body": msg,
        }
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")


def install():
    import smtplib

    smtplib.SMTP = _FakeSMTPInstance
