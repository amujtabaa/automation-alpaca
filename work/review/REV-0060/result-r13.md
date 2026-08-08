# Independent R13 RED-contract pre-flight result

**Review posture:** static, independent, and documentation-only. I did not run
tests, application code, database/SQL, or network activity. This result reviews
only the immutable candidate set named by
`WO-0151-RED-CANDIDATE-R13-MANIFEST.md`; it grants no implementation,
ratification, activation, or closeout authority.

## Integrity and candidate conditions

**PASS.** The manifest is the exact working-tree file with SHA-256
`923b23945627e87372e0f9d6e28255247cb3cbaaa4637b9a2cdb272425a5ec95`.
All 29 listed SHA-256 pins match their named files. The candidate conditions
also hold: no staged path; the only tracked application/test delta is the
listed frozen `tests/execution_core/test_acquisition_stateful.py` detector;
and `result-r13.md` was absent before this review. The detector and its freeze
record were read only as negative evidence and were neither executed nor
modified.

## Re-derived failure and correction path

The frozen public trace is coherent with the current code. A completed A to B
successor first creates a sealed successor registration from the pre-rollover
venue context (`app/execution_core/acquisition.py:4043`,
`app/execution_core/authority.py:5628`, and
`app/execution_core/authority.py:5924`). Current registration publishes B
without a venue transition. On B's first canonical BUY fact, the unchanged
ordinary projector requires the proof cursor mandate to equal B's mandate
(`app/execution_core/protection.py:4245`); the retained cursor is still A, so
the composite correctly refuses. That is the frozen E2 defect, not an E3
fixture defect.

R13 supplies a bounded, constructible repair:

- The venue owns the new zero-economic transition and direct cursor mutation
  (`app/execution_core/venue.py:8103`, `:8563`), while ordinary mandate-change
  refusal remains intact.
- Authority remains the sole composer after its existing completed-flat gates
  (`app/execution_core/authority.py:5924`). A sealed pre-rollover successor
  registration can bind the venue proof; the authority can then derive the
  post-rollover B entry from the same authenticated coordinates and bind both
  that result and the one transition in the receipt. This is one directional
  chain—pre-registration, venue proof, post-rollover state/receipt—not a
  cyclic proof.
- The current acquisition composite already owns the receipt validation seam
  (`app/execution_core/acquisition.py:2366`, `:4208`). R13 can require exactly
  one transition only for completed successors and zero for the existing
  aborted/unrooted route without adding a public API.
- The proposed private direct-scope cursor/currentness predicate belongs at
  the central authority projection (`app/execution_core/authority.py:2918`),
  so an old A book paired with B currentness becomes non-serving without a
  collection or history scan.

The R13 cursor is a new, predecessor-linked venue provenance transition with
B's distinct mandate; it is not a transfer of A's normal protection state,
market-stream cursor, capacity, policy, or market-evidence authority. That is
consistent with ADR-021's fresh-B requirement and ADR-023's market-occurrence
boundary.

## Boundary and control assessment

**PASS.** FR-01 through FR-05 and AC-01 through AC-08 cover the material
failure modes: copied/raw registration material, ordinary proof reuse, direct
private call/import exposure, mismatched scope or mandate, non-flat or
unreconciled predecessor, duplicate/missing transition, cross-bound receipt,
stale-book serving, aborted rollover, and late-A fact handling. The proposed
test paths are an allowlist, not a requirement to edit every listed test file;
a narrower implementation test delta is acceptable only if it still provides
the named behavior, mutation, and static-boundary controls. Therefore the
broader list is not a scope or constructibility P1.

The contract preserves no-public-API, no-authority-side-duplicate-index,
no-acquisition-private-venue-import, and no-history-scan boundaries. It also
keeps the frozen E3 detector downstream and unchanged.

## Evidence limits

This is a static RED-contract acceptance, not implementation evidence. The
future implementation must make the listed RED and mutation controls fail for
their named reasons, then satisfy the work-order gates before the frozen E3
detector may be rerun.

## Verdict

**ACCEPT**

- P0: 0
- P1: 0
- P2: 0

The exact R13 contract and manifest may proceed to their separate human
ratification and activation gates. No source or test implementation is
accepted by this result.
