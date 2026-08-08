---
type: Review Request Addendum
rev_id: REV-0048
addendum: 04
title: "WO-0146 complete retained-graph Python 3.11 repair"
status: AWAITING_REVIEW
failed_target: 4b9b47de1936a179478f1c638c4872a4b0935719
blocked_target: 1189d88
reviewed_target: 5a8984133354ecfa0343d6fb4a7fdaef38d56dab
base: fe85336c962e13ba34a57c52856c65bda4fa83a7
date: 2026-08-02
---

## Independent assignment

Review the bounded final repair at `fe85336..5a89841`, its complete recovery chain from failed
candidate `4b9b47d`, and the exact evidence in
`implementation-evidence-python311-compat-fix-02.md`. Do not edit the request, evidence, WO, PKL,
ledger, implementation, or any earlier reviewer result. Deposit findings only as
`result-addendum-04.md`.

Addendum-03 and the independently blocked `1189d88` freeze remain admissible negative evidence. Do
not overwrite or reinterpret them. Pre-register and attack these properties:

1. The oracle is Python-3.11-safe: no recursive rendering or traversal of persistent graphs.
2. Every behavior-bearing retained field, direct map, sequence backing map, cached node value, and
   alias relationship is visible to the immutable-input projection.
3. The same complete projection rejects structurally divergent second-call outputs even where
   ordinary index equality omits auxiliary caches.
4. Hostile cycles terminate deterministically; sibling ordering and independently equivalent graphs
   do not create false acceptance or false divergence.
5. The production execution-core tree is unchanged, and no production call path depends on the
   equality omission in a way that leaves a P1.
6. The RED-to-GREEN record, counts, artifact hashes, scope, and lifecycle posture are exact.
7. WO-0146 remains effectively `REVIEW`, WO-0147 remains inactive, and exact-head Python 3.11/3.12
   successor CI remains external.

Independently inspect the exact and cumulative diffs. Run the focused controls and complete
stateful file at a reduced recursion limit. Create fresh counterexamples against at least one
direct auxiliary map, one sequence-backed map, cached node metadata, alias topology, a cycle, and
second-output divergence. Verify the production equality call sites and evidence hashes. You may
independently rerun broader gates, but do not treat implementation-seat claims as reproduced unless
you do so.

Every P0/P1 requires file:line, impact, and exact resolution. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`. Even `ACCEPT` does not satisfy the external exact-head dual-CI
gate.
