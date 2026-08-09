# Ruling needed: OQ-002 — Does the FastAPI rewrite need to implement authentication, or does an upstream proxy handle it?

**What's being decided.** Whether the new backend needs to verify who's calling it, or whether
that's already handled by something in front of it today and should stay that way.

**Why it's ambiguous.**
- Reading A — **No auth needed in the app.** Every request in the sampled access log carries
  the same populated identity field (`jdoe@corp.example.com`), in the position an authenticating
  reverse proxy's injected identity would sit (Apache's `%u` remote-user convention). That's
  consistent with — but not proof of — a proxy in front of ticketd handling authentication
  today, with the app itself trusting whatever identity arrives.
- Reading B — **The app is genuinely unauthenticated today**, and that's a real gap tolerated
  only because it's "internal." Evidence: `ticketd/app/server.py` has zero authentication or
  authorization code — no session handling, no token verification, no credential check —
  across all 7 routes. Every route is reachable by anyone who can reach the network.

Nothing in the legacy tree settles this either way; it's the kind of fact that lives in
infrastructure/deployment configuration this generator never had access to.

**Where it bites.** Doesn't block Milestone 0 (the walking skeleton is scoped to be answerable
either way — see `docs/features/WO-001-walking-skeleton.md`). Affects every work order past M0
that touches request identity, session handling, or anything security-adjacent — which in
practice is most of Milestone 1 (the reset-token flow in particular). Flags gate review rather
than hard-blocking, per `root CLAUDE.md`'s known-blockers section.

**Options & consequences.**
1. **Confirm reading A (proxy handles it).** The rewrite adds nothing — no auth code, same
   assumption as today. Fastest path; carries forward today's risk profile unchanged (whatever
   that risk profile actually is, which this workspace can't independently verify).
2. **Confirm reading B (genuinely open) and ask for auth to be added.** New, real scope not
   currently in any PB entry or work order — would need its own PB entry and backlog additions
   before an executor could build it (building it speculatively right now would be unsanctioned
   scope creep per this workspace's own rules).
3. **Defer past M0, rule before M1's auth-adjacent work orders start.** Lets the walking
   skeleton prove the stack choice without this decision on the critical path, at the cost of
   revisiting it soon.

**Recommendation (non-binding).** This reads more like an infrastructure/deployment question
than a code question — whoever owns the network path in front of ticketd today (load balancer
config, ingress rules, a proxy's auth module) likely has a fast, confident answer that no
amount of additional code archaeology here would produce. Worth a five-minute conversation with
whoever runs ticketd's production deployment rather than further analysis of this repository.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
