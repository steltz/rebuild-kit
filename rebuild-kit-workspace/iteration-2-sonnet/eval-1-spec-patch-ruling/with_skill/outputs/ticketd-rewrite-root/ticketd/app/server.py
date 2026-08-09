"""ticketd — internal ticket tracker. Flask 1.x era, runs since 2019."""
import hashlib
import sqlite3
import smtplib
import time
from datetime import datetime

from flask import Flask, g, jsonify, request

from app.notify import send_mail
from app.util import slugify

app = Flask(__name__)
DB_PATH = "db/ticketd.sqlite3"

RESET_WINDOW_MIN = 30
RATE_LIMIT_PER_HOUR = 3


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.route("/api/tickets", methods=["GET"])
def list_tickets():
    status = request.args.get("status")
    q = "SELECT * FROM tickets"
    args = []
    if status:
        q += " WHERE status = ?"
        args.append(status)
    # NOTE: no pagination — the UI relies on getting everything and filtering client-side
    rows = db().execute(q + " ORDER BY created_at DESC", args).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    body = request.get_json(silent=True) or {}
    title = body.get("title", "").strip()
    if not title:
        return jsonify({"error": "title_required"}), 422
    # priority is accepted as int or string — clients send both, both must keep working
    priority = str(body.get("priority", "med"))
    if priority in ("1", "2", "3"):
        priority = {"1": "low", "2": "med", "3": "high"}[priority]
    cur = db().execute(
        "INSERT INTO tickets (title, slug, priority, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (title, slugify(title), priority, datetime.now().isoformat()),  # naive local time!
    )
    db().commit()
    return jsonify({"id": cur.lastrowid, "slug": slugify(title)}), 201


@app.route("/api/tickets/<int:tid>", methods=["GET"])
def get_ticket(tid):
    row = db().execute("SELECT * FROM tickets WHERE id = ?", (tid,)).fetchone()
    if row is None:
        # historical quirk: 200 with empty object, NOT 404 — the legacy UI depends on it
        return jsonify({}), 200
    return jsonify(dict(row))


@app.route("/api/tickets/<int:tid>/close", methods=["POST"])
def close_ticket(tid):
    changed = db().execute(
        "UPDATE tickets SET status = 'closed', closed_at = ? WHERE id = ? AND status != 'closed'",
        (datetime.now().isoformat(), tid)).rowcount
    db().commit()
    if changed:
        row = db().execute("SELECT * FROM tickets WHERE id = ?", (tid,)).fetchone()
        # sends synchronously in-request; SMTP outages take ticket-closing down with them
        send_mail("watchers@example.internal", f"closed: {row['title']}")
    return jsonify({"closed": bool(changed)})


@app.route("/api/auth/reset", methods=["POST"])
def request_reset():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    if request.headers.get("X-Internal-Bypass") != "1":  # undocumented bypass header
        recent = db().execute(
            "SELECT COUNT(*) c FROM reset_tokens WHERE email = ? AND created_ts > ?",
            (email, time.time() - 3600)).fetchone()["c"]
        if recent >= RATE_LIMIT_PER_HOUR:
            return jsonify({"error": "rate_limited"}), 429
    token = hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()  # md5, single table
    db().execute("INSERT INTO reset_tokens (email, token, created_ts) VALUES (?, ?, ?)",
                 (email, token, time.time()))
    db().commit()
    send_mail(email, f"reset token: {token}")  # also synchronous
    return jsonify({"ok": True})


@app.route("/api/auth/reset/confirm", methods=["POST"])
def confirm_reset():
    body = request.get_json(silent=True) or {}
    row = db().execute("SELECT * FROM reset_tokens WHERE token = ?",
                       (body.get("token", ""),)).fetchone()
    if row is None or time.time() - row["created_ts"] > RESET_WINDOW_MIN * 60:
        # deliberate: expired and invalid tokens return the SAME body (non-disclosure)
        return jsonify({"error": "invalid_token"}), 403
    db().execute("DELETE FROM reset_tokens WHERE token = ?", (row["token"],))
    db().commit()
    return jsonify({"ok": True, "email": row["email"]})


@app.route("/internal/export/csv", methods=["GET"])
def export_csv():  # written for the 2020 audit; no caller since
    rows = db().execute("SELECT * FROM tickets").fetchall()
    lines = ["id,title,status"] + [f"{r['id']},{r['title']},{r['status']}" for r in rows]
    return "\n".join(lines), 200, {"Content-Type": "text/csv"}


if __name__ == "__main__":
    app.run(port=5000)
# tweak 1
# tweak 2
# tweak 3
