# **Auth/Reset** (designed-not-built)

Not implemented yet — see `docs/features/WO-003-reset-token-mechanism.md`,
`WO-007-auth-reset-request.md`, `WO-008-auth-reset-confirm.md`.

**Designed to hold, unchanged**: the rate limit math, the undocumented bypass header (preserved
as-is pending OQ-006), the non-disclosure behavior (identical response for unknown vs. expired
tokens), single-use consumption, and the 30-minute expiry window.

**Designed to change**: tokens will be CSPRNG-generated and stored hashed, in a properly keyed
and indexed table with a database-level expiry column — replacing the MD5-of-email-plus-
timestamp scheme entirely (PB-002). No response body ever carried the raw token, legacy or
modern, so this change is invisible at the HTTP boundary; it only shows up in what's sitting in
the database.

**Still open**: whether the confirm endpoint should gain rate limiting it doesn't have today
(OQ-009), and whether the app needs to implement authentication at all versus continuing to
assume an upstream proxy handles it (OQ-002) — this second one is flagged for a ruling before
Milestone 0 if at all possible, since it's structural rather than a detail.
