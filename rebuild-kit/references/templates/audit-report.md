# Template: audit/report.md (+ metrics.json)

```markdown
# Adversarial Audit Report — <system name>
<!-- Generated P9. Fresh-context auditors; inputs: legacy tree, problem brief, draft specs only. -->

## Scorecard
| Metric | Value |
|---|---|
| Claims audited / confirmed / contradicted / unverifiable | n / n / n / n |
| Claims confirmed | nn% |
| Spec branch coverage (branches in source represented in specs) | nn% |
| Problem coverage (PB entries dispositioned) | nn% (must be 100 to assemble) |
| Demotion rate (claims → ASK) | nn% |

## Per-module results
| Module | Claims | Confirmed | Demoted | New coverage items | Notes |
|---|---|---|---|---|---|

## Discrepancies (each has been applied to the specs — this is the record)
### AD-001 — <claim> (WO/spec ref)
- verdict: contradicted | unverifiable
- counterexample / gap: <the input, flag state, or code path — cited>
- action taken: demoted to ASK → OQ-nnn | spec item added | do-not-port candidate

## Coverage-hunt findings
<branches/flags/error paths in source with no spec, and where each was routed>

## Fixture spot-check
<sampled fixtures validated; failures and fixes>
```

`audit/metrics.json` carries the scorecard numbers verbatim (keys:
`claims_confirmed_pct`, `branch_coverage_pct`, `problem_coverage_pct`, `demotion_rate`) —
copied into `ledger.json.audit` so gate-signing humans see how hard the docs were attacked.
