# REV-0116 R3 root correction — establish C1 before reconciliation

Date: 2026-08-29

Status: **R2 P1 ACCEPTED — corrected contract pending finite verification**

The first compact successor is now the prerequisite for reconciliation, not its consequence. One
private transaction authenticates C0 plus fresh proof, constructs compact current owners, applies
cold market invalidation, commits C1, and rereads C1. Only C1 can enter the existing M2-I4
reconciliation path, so ordinary checkpoint authentication remains intact.

After all targeted reconciliation operations and complete current-proof reload, startup invokes
the same private cold-invalidation transition against the latest context. If invalidation remained
current, this is exact replay with no head advance. If an admitted recovery transition changed the
relevant current protection state, it commits and rereads one final invalidated successor. No
source method is called before that final barrier returns normally.

The failure-capable matrix now includes C0 with one unresolved claimed effect whose returned
recovery operation changes the checkpoint, plus rollback, ambiguous-commit, source-refusal/retry,
and no-extra-advance controls. No new operation domain, public API, DDL, table, replay store,
callback, or alternate engine is introduced.
