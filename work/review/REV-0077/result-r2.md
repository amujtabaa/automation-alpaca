# REV-0077 R2 reconciled result

Date: 2026-08-23

Candidate: `bdacfb2fcf2f22e202c8220874722e8e71f8ec92`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=11`, `P2=1`)

Three fresh-context read-only reviewers verified the candidate and reviewed authority/wire,
persistence/DDL, and implementability without SQLite. Duplicate findings are reconciled below.

## P1

1. Outer scope wire says durable atom for integer `scope_id`; the full outer row must be inlined.
2. Sentinel fields plus public unkeyed bindings are copy-forgeable; issuance needs a private
   identity registry and copied/recomputed-binding mutants.
3. Selection proofs are not transaction/connection current. Store must freshly reselect and compare
   the complete selection commitment before payload/CAS.
4. Target head is caller-shaped rather than derived from durable controller/protection currentness.
5. Owner-only inactive descriptors/bootstrap/source references cannot all be database-point-
   validated by the pre-projection set; provenance classes must be narrowed exactly.
6. Q1-Q9 remain prose categories, not complete executable SQL with exact flattened storage vectors,
   closure-head logic, parameter order, absence rules, and plan assertions.
7. `MATERIALIZED qualifying_effect` can do unbounded refusal work; Q3 counters must gate it first
   and disjoint arms must use `UNION ALL`.
8. Combined found-plus-absence rows can overflow while each legal family remains under its cap;
   derive absence as the complement of independently capped found vectors.
9. Per-application genesis version 1 conflicts with globally unique kernel checkpoint versions;
   DDL must make versioning application-scoped.
10. Payload-first/CAS cannot guarantee rollback when a caller commits non-`APPLIED`; WO-0168c must
    narrow its guarantee and WO-0168b must name the production rollback owner.
11. Retained inactive authority descriptors require explicit payload-owned treatment or a durable
    current-reference relation; they cannot silently disappear or be falsely database-proven.

## P2

The execution component has seven map/order commitments before its final state commitment, not six.

## Unverified

No SQLite, query plan, changed-DDL installation, runtime test, or concurrency/fault test ran. R2
grants no source or database authority.
