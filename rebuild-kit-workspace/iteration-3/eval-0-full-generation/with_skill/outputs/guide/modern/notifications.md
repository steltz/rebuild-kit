# **Notifications** (designed-not-built)

**Not yet built.** Designed in `docs/features/WO-001-notification-decoupling.md` — the whole
reason this rewrite exists (PB-001).

The design requirement is simple to state and easy to get subtly wrong: no HTTP handler may block
on notification delivery, but the underlying business transaction (ticket closed, token issued)
must stay durable regardless of delivery outcome — that part legacy already got right (commit
happens before send) and must not regress. What's new is durability *of the notification itself*
across a process crash, which legacy never had. The exact mechanism (an outbox table, a real
queue, a framework-native background task) is a FREE choice; what's fixed is the outcome.

One thing worth flagging for whoever builds this: the replay harness (`verification/harness/`)
can't yet observe notification dispatch over plain HTTP — this WO is also responsible for giving
the harness a way to check it, or ED-001/ED-001b will pass trivially without actually verifying
anything (see `verification/README.md`'s documented gap).
