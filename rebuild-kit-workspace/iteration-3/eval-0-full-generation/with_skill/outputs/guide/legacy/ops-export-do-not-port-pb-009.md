# **Ops/Export** *(do-not-port — PB-009)* (how it works today)

One route, `GET /internal/export/csv`: dumps every ticket's id/title/status as CSV, no auth, no
pagination. Its own code comment says it was "written for the 2020 audit; no caller since" —
and the 2,000-request access-log sample backs that up with zero hits. Two independent signals
(dead-caller comment + zero traffic) clear the do-not-port bar (PB-009). It's not carried into the
rewrite. The one asterisk: the access log covers a single day, not the genuine month the original
rewrite request described, so a human should confirm nothing out-of-band (a quarterly script,
say) still hits this before legacy is actually decommissioned — see OQ-003.
