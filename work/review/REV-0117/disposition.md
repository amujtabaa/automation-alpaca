# REV-0117 round-one author disposition

Date: 2026-08-29

Status: **all four findings accepted for one bounded root-remediation round**

The independent `result.md` is preserved unchanged. This disposition does not convert the review
to acceptance; only the finite exact-head correction review may do that.

## P0-1 — accepted evidence defect; corrected without rewriting reviewer evidence

- The request's unqualified `git diff --check` claim was false. It is retracted.
- Ruff formatting was applied to the complete predecessor-to-candidate Python inventory; the only
  pre-remediation production miss was `app/execution_core/position.py`.
- `work/review/REV-0116/result.md` is reviewer-owned and immutable under the repository's review
  policy. Its historical blank EOF is therefore disclosed and excluded from any new green claim,
  not silently rewritten to satisfy a mechanical check.
- Correction evidence must separately report the complete-range preserved exception and a clean
  check over every author-controlled remediation path. No future packet may describe a
  hand-selected subset as the full range.

## P1-1 — accepted owner-fence defect; root corrected

Every retained source-currentness call now passes through one private helper that checks the exact
owner lease immediately before and after that single external call. The post-baseline datastore
reread is fenced before and after, and connection close is fenced before with an immediate
post-close owner check before any source call or serving publication.

Fresh negative controls lose ownership as the post-baseline reread returns, during the first of
two retained source-currentness calls, and during connection close. They require `OWNER_LOST` and
prove no later external source capability or serving publication occurs.

## P1-2 — accepted frozen-boundary drift; explicitly reconciled

The work-order scope now names the two guard tests. Their exact frozen inventories admit only
`tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py` as the new setup-capability
and held-SQLite boundary. Existing canaries and all other allowlist entries remain unchanged.

## P1-3 — accepted stale oracle; validation remains two-layered and fail-closed

WO-0169 intentionally decodes an internally authentic but inert checkpoint state before binding it
to fresh direct proof. Mutating raw quantity, tail-fold input, or integrity ordering while retaining
the old state commitment therefore fails at the first layer with `execution state is not
authentic`. The test now names that exact first-layer refusal. Its separate foreign-proof case is
unchanged and still requires `direct proof state commitment does not match state`, preserving a
failure-capable pin for the second layer. No production validation was weakened.

## Finite stop

This is the sole remediation round permitted by the original request. The correction review is
limited to these four findings and regressions introduced by their fixes. Zero open P0/P1 is
required before the separate SQLite execution gate; otherwise WO-0169 stops for explicit
re-diagnosis rather than entering another review loop.
