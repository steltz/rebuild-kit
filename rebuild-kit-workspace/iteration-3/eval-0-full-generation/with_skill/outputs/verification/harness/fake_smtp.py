"""Stub SMTP for twin-boot runs -- neither legacy nor modern should ever talk to a real mail
server during verification. Import this BEFORE importing app code that imports smtplib, so the
monkeypatch is in place before `from smtplib import SMTP`-style imports bind the real class.

Used by run-legacy.sh today. run-modern.sh should use the equivalent for whatever notification
library the modern stack ends up using (FREE choice, WO-001) -- this file only covers legacy's
smtplib-based `app/notify.py`.
"""
import json
import os
import smtplib

SENT_LOG = os.environ.get("TICKETD_FAKE_SMTP_LOG", "/tmp/ticketd_harness_sent_mail.jsonl")


class FakeSMTP:
    def __init__(self, host, port, timeout=30):
        self.host, self.port, self.timeout = host, port, timeout

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def sendmail(self, from_addr, to_addrs, msg):
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps({"from": from_addr, "to": to_addrs, "body": msg}) + "\n")


smtplib.SMTP = FakeSMTP
