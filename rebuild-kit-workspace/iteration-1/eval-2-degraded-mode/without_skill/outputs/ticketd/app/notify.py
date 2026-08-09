"""SMTP notifier. Blocks the request thread; ~2s typical, 30s on provider trouble."""
import smtplib


def send_mail(to, body):
    with smtplib.SMTP("smtp.internal", 25, timeout=30) as s:
        s.sendmail("ticketd@example.internal", [to], body)
