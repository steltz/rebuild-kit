#!/usr/bin/env python3
"""Test hook (legacy side): age reset tokens so expiry is testable without waiting.
Usage: age_token_sqlite.py --db path --email a@b --seconds 3600
Modern side must provide the equivalent (modern/harness-age-token.sh EMAIL SECONDS) —
see verification/harness/README.md.
"""
import argparse
import sqlite3

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--email", required=True)
ap.add_argument("--seconds", type=float, required=True)
a = ap.parse_args()
con = sqlite3.connect(a.db)
n = con.execute("UPDATE reset_tokens SET created_ts = created_ts - ? WHERE email = ?",
                (a.seconds, a.email)).rowcount
con.commit()
print(f"aged {n} tokens for {a.email} by {a.seconds}s")
