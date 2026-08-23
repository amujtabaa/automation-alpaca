# REV-0075 R2 — WO-0168a owner-proof remediation review result

Reviewer disposition: **ACCEPT-WITH-CHANGES**

Exact candidate reviewed: `7ce59209f7ac673477a766e42ccd5b2a54406749`, tree
`fb5d8278f1338ae0fd5d56a557308fb3dc9411bf`, against parent
`7fa6c2a9c5ce63a3e40362c55f5919b1d88cd6db`.

## Findings

### P1 — Execution proof hashes aggregates but does not prove direct-row membership

Location: `app/execution_core/position.py:1125`

The direct-proof seam verifies a self-consistent proof commitment and aggregate hash equality, but
holds no keyed membership/non-membership witness and no retained index to verify that the prior
observation, root head, predecessor, and root claim are the rows committed by those aggregates. A
self-consistent substituted or stale slice therefore remains indistinguishable. The root correction
is a bounded exact membership/non-membership proof for every selected/absent row, verified against
the retained aggregate commitments, or an owning hydration seam that performs the keyed lookups
before classification.

### P1 — Protection proof remains caller-selected and accepts stale or mis-profiled coordinates

Location: `app/execution_core/protection.py:2577`

The directly constructible current-row carrier is validated only for relationships within caller
data. The hydrator does not authenticate application generation, execution profile, scope ID,
authority class, version, or controller head against retained current rows. A self-consistent but
wrong selection can therefore hydrate. The root correction is owner-only issuance over authenticated
persistence-adapted current rows, with every selected envelope/currentness/authority coordinate
verified before the hydrator receives a proof; tests must include well-typed, internally consistent
substitutions.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

Unverified: broader fill/stateful/protection suites, ruff, and mypy were not re-run by the reviewer.
The reviewer performed no SQLite/DDL, runtime composition, network/broker activity, commits, or
edits.
