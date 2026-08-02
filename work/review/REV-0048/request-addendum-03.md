---
type: Review Request Addendum
rev_id: REV-0048
addendum: 03
title: "WO-0146 Python 3.11 closeout compatibility repair"
status: AWAITING_REVIEW
failed_target: 4b9b47de1936a179478f1c638c4872a4b0935719
reviewed_target: ba70c46b05f3ec3d653159f00193c03711ba82e7
base: a7dbc0390a0cf3f06c0769b29389de34ea2fed10
date: 2026-08-02
---

## Independent assignment

Review only the bounded Python 3.11 compatibility repair at
`a7dbc0390a0cf3f06c0769b29389de34ea2fed10..ba70c46b05f3ec3d653159f00193c03711ba82e7`
and its relationship to the failed exact-head run. Do not edit the request, implementation,
evidence, WO, PKL, or ledger. Deposit findings only as `result-addendum-03.md`.

Pre-register and attack these properties:

1. The fix removes the recursive Python 3.11 rendering path without changing production.
2. Determinism and immutable-input mutation detection are not weakened.
3. Component commitments cover semantic state, and bounded binding/fact snapshots cover fields
   excluded from those commitments.
4. A malicious reducer mutation of component state, a binding, or fact payload is still detected.
5. Scope, evidence, and closeout posture truthfully keep WO-0146 in effective `REVIEW` and WO-0147
   inactive after run #682 failed.

Independently inspect the exact diff, reproduce the three exact nodes and full stateful file, run
Ruff/diff/scope checks, and perform at least one fresh mutation or counterexample against the new
guard. Verify the failed GitHub trace and the evidence hashes where accessible. Do not treat the
implementation-seat full/R2 claims as independently reproduced unless you actually run them.

P0/P1 findings require file:line, impact, and exact resolution. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`. Exact-head Python 3.11/3.12 successor CI remains an external
gate even if this implementation diff is accepted.
