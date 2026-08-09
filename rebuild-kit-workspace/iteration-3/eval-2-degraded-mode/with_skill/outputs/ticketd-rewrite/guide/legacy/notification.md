# Notification (how it works today)

The entire notification subsystem is seven lines (`legacy/app/notify.py`): open a plaintext SMTP
connection to `smtp.internal:25`, send, close. Its own docstring is the clearest evidence in the
codebase for why this is the rewrite's headline defect: "Blocks the request thread; ~2s typical,
30s on provider trouble." Two call sites use it — ticket-close and reset-request — both
synchronously, both before returning a response, both with zero retry logic. An unreachable SMTP
server doesn't degrade these two endpoints; it takes them down (confirmed live during generation:
booting legacy against an unroutable SMTP host produces an unhandled exception and a raw 500).
