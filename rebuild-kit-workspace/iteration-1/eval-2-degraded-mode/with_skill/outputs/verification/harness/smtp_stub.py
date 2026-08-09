#!/usr/bin/env python3
"""Minimal capturing SMTP server (stdlib only; Python 3.12+ has no smtpd module).

Speaks just enough SMTP for smtplib.sendmail(): 220 greeting, 250 to HELO/EHLO/MAIL/RCPT,
354 to DATA, capture until lone '.', 250, 221 on QUIT. Every accepted message is appended
as one JSON line to --log: {"to": [...], "from": ..., "data": "..."}.

Used by run-legacy.sh (and available to modern implementations that choose real SMTP in
tests). Harness instrumentation only — never deployed.
"""
import argparse
import json
import socket
import threading


def handle(conn, log_path, lock):
    f = conn.makefile("rb")
    conn.sendall(b"220 harness-stub ESMTP\r\n")
    mail_from, rcpt, data_mode, data = None, [], False, []
    for raw in f:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if data_mode:
            if line == ".":
                with lock, open(log_path, "a") as fh:
                    fh.write(json.dumps({"from": mail_from, "to": rcpt,
                                         "data": "\n".join(data)}) + "\n")
                mail_from, rcpt, data_mode, data = None, [], False, []
                conn.sendall(b"250 OK\r\n")
            else:
                data.append(line[1:] if line.startswith("..") else line)
            continue
        verb = line.split(":")[0].split(" ")[0].upper()
        if verb in ("HELO", "EHLO"):
            conn.sendall(b"250 harness-stub\r\n")
        elif verb == "MAIL":
            mail_from = line.split(":", 1)[1].strip().strip("<>")
            conn.sendall(b"250 OK\r\n")
        elif verb == "RCPT":
            rcpt.append(line.split(":", 1)[1].strip().strip("<>"))
            conn.sendall(b"250 OK\r\n")
        elif verb == "DATA":
            data_mode = True
            conn.sendall(b"354 end with .\r\n")
        elif verb == "QUIT":
            conn.sendall(b"221 bye\r\n")
            break
        else:
            conn.sendall(b"250 OK\r\n")
    conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    open(args.log, "w").close()
    lock = threading.Lock()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(8)
    print(f"smtp-stub listening on 127.0.0.1:{args.port} → {args.log}", flush=True)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn, args.log, lock), daemon=True).start()


if __name__ == "__main__":
    main()
