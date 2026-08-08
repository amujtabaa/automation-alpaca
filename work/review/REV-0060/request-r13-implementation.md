# Independent acceptance request -- WO-0151 R13 implementation

Review the exact local implementation candidate defined by
`WO-0151-R13-IMPLEMENTATION-CANDIDATE-MANIFEST.md` at SHA-256
`b8fa0ab942ca32ec1a4aabb3c3f8d352ff33980437e72b456f26b5695ad11b8c`.

## Review boundary

- Branch: `codex/arch-reset-2026-07-r1`.
- Review base: `2208119083632ce26e58f966f6d7c3f3775f4aa7`.
- Authority: R13 contract
  `240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90`,
  clean R13-R1 manifest
  `c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222`,
  semantic `ACCEPT`
  `71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5`,
  and activation R1 `ACCEPT`
  `82627d88422374f0230e8f00926b397b06104b32042a993ea21f453fc9403c59`.
- Candidate paths are exactly the eight paths and hashes in the candidate
  manifest. Treat every other tracked or untracked path as excluded context.

The only permitted reviewer write is
`work/review/REV-0060/result-r13-implementation.md`. Do not edit application,
tests, work orders, candidate evidence, PKL, ledger, ratification, frozen E3
artifacts, or historical raw manifests. Record `ACCEPT`,
`ACCEPT-WITH-CHANGES`, or `BLOCK` with P0/P1/P2 counts and evidence limits.

## Required re-derivation

1. Rehash the candidate, authority pins, frozen detector, and review base;
   distinguish the excluded pre-existing detector delta from the exact R13
   candidate.
2. Read the R13 contract, retained WO-0151 authority, accepted ADR-020 R2,
   ADR-021 R2, ADR-023 R1, and the direct venue/authority/acquisition semantic
   centers before relying on evidence prose.
3. Prove the completed A-to-B rollover is venue-owned, zero-economic,
   predecessor-linked, registration-bound, receipt-bound, exactly one
   transition, and atomically co-published with B currentness.
4. Prove aborted successors remain zero-transition, old-A-book/B-currentness
   is non-serving, no-currentness refresh remains structurally valid, and no
   public or generic route can mint rollover authority.
5. Disprove wrong scope/mandate, nonflat/inconsistent execution, ownership,
   source-binding, duplicate transition, copied/rebound proof, ordinary mandate
   change, and serving-predicate bypasses against their failure-capable controls.
6. Trace B's unchanged first-fill projector and late retired-A facts both before
   and after B's first fill. Confirm B remains the sole live generation, A
   lineage/economics advances exactly once, and `HARD_BAIL` creates no normal B
   capacity.
7. Adjudicate the exact waiting-resolution branch: an open/unknown B parent is
   preserved without invented cancellation authority, while safe stand-down or
   cancellation retains the existing atomic preemption route.
8. Confirm no public API/export, venue-to-authority import, history scan,
   controller history, runtime/persistence/database/network path, or E3 source
   edit was introduced.
9. Verify the disclosed premature detector collection is treated only as a
   process error/negative diagnostic event and that only the final clean full
   pure-suite rerun supports local success.

You may run focused pure tests and static/type/import checks. Do not edit or
execute the frozen `test_acquisition_stateful.py` detector during this review;
its exact source may be inspected read-only for downstream constructibility.
Do not run database-capable fixtures, SQL/DDL, broker/network activity, runtime
wiring, external CI, cleanup, or destructive commands.
