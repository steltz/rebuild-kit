# Auth/Reset (designed-not-built)

`WO-003` replaces the MD5 token with a CSPRNG (`secrets.token_urlsafe` or equivalent) while
preserving every externally observable outcome exactly: same rate limit, same 30-minute window,
same identical-body non-disclosure on invalid/expired tokens, same single-use-by-deletion
semantics. The email dispatch call moves onto `WO-004`'s async boundary (see
`guide/modern/notification.md`).

**Not implemented and not scheduled**: the `X-Internal-Bypass` header. `WO-003` is
`awaiting_ruling` on `OQ-001` — neither reading (keep-with-real-auth vs. drop-entirely) has been
built, on purpose. This work order cannot close until a human rules.

No implementation exists yet.
