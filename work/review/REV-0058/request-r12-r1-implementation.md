# Independent acceptance request — WO-0151 R12-R1 implementation

Review the exact local implementation candidate defined by
`WO-0151-R12-R1-IMPLEMENTATION-CANDIDATE-MANIFEST.md` at SHA-256
`abe0df5d723df536263e99a72d1b612ffcf39032de71753aaee9a6304e8166f0`.

## Review boundary

- Branch: `codex/arch-reset-2026-07-r1`
- Review base: `f25505cb59afde42e312a3933b85e44e6ad44c41`
- Authority: R12-R1 contract
  `9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25`,
  R12-R1 semantic acceptance
  `5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b`,
  and the accepted R12-R1 activation R2 result
  `ef5ba3af97bc76b2e1f77fa4bab0fc9d4677f5dfc7f8eb740c2e5c9dad688444`.
- Candidate paths are exactly the six paths and hashes in the candidate
  manifest. Treat every other tracked or untracked path as out of scope.

The only permitted reviewer output is
`work/review/REV-0058/result-r12-r1-implementation.md`. Do not edit the
candidate, work-order, test, application, PKL, ledger, ratification, or frozen
E3 artifacts. Record a verdict of `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`
with P0/P1/P2 counts and evidence limits.

## Required re-derivation

1. Rehash all candidate paths and the manifest; confirm the local base and
   scope shape.
2. Read the applicable R12-R1 contract, retained WO-0151 authority, accepted
   ADR-020 R2 and ADR-021 R2, and direct semantic centers in `fills.py` and
   `acquisition.py`.
3. Re-derive the presence distinction: only physical absence is fresh; a
   present `None`, wrong runtime value, wrong key, or mismatched binding cannot
   admit a stream-reused successor.
4. Check that the stream registry relation is direct, sealed, scope-owned, and
   retained through record replacement without a history scan or an
   authority-side duplicate index.
5. Distinguish malformed candidate-route handling (ordinary exact `REFUSED`)
   from malformed current-route handling (invalid unauthentic input); validate
   value-equivalent immutable copies remain valid.
6. Assess the five test surfaces, including whether the moved bounded-map
   provenance guard still has a failure-capable target.
7. Confirm the unchanged WO-0152 detector and evidence remain frozen and that
   the paired 93% external-coverage condition remains deferred.

You may reproduce focused pure Python tests and static checks where useful.
Do not run SQL/DDL, database-capable fixtures, broker/network activity,
runtime wiring, the WO-0152 E3 detector, external CI, or cleanup operations.
Do not rely on historical test output as a substitute for fresh evidence.
