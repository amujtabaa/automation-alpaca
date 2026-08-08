# REV-0058 R9 independent pre-flight result

Status: **ACCEPTED PRE-FLIGHT EVIDENCE -- DOCUMENTATION ONLY**

## Exact candidate and integrity

- Review base / current reviewed HEAD: `a95af72ee8d7a41f8e0b7859f5124c8a9e929548` on
  `codex/arch-reset-2026-07-r1`.
- R9 manifest: `d108bec898d58a0d48841f874b7b03009c926ac5efdeb87ea38565f3662e14b7`.
- R9 contract: `168ebd0478faa6abb326f56859ff5efb64b3b66517ff72eade1f51b99f3a5479`.
- R9 request: `7767be192f2effd4a60540dab3e884583d7442763abf38c761e087e33853a69f`.

The manifest self-hash and all 22 manifest-listed hashes matched exactly:

| Artifact | SHA-256 |
|---|---|
| `docs/adr/ADR-020-current-state-execution-kernel.md` | `eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653` |
| `docs/adr/ADR-021-position-protection-liquidity-execution.md` | `b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c` |
| `docs/adr/ADR-023-bounded-market-occurrence-authority.md` | `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf` |
| `work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md` | `1b54a86a96e3f3259fbfc5c0c6b8cad16af100b929c4466a92dd633e9546dcd3` |
| `work/review/REV-0058/WO-0151-RED-CANDIDATE-R8-MANIFEST.md` | `b6faddc624a227382f80ebefe57044ce2e2e372328df3528e027fc4bcd924311` |
| `work/review/REV-0058/result-r8.md` | `5dc43bcaab99af837ee89e83880a1484cb79f649ea67e7218e5a2dd798699e80` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R2.md` | `343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R3.md` | `8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R4.md` | `bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R5.md` | `a83bf31578e66b92fdb0e0f27987b9070a127037be2f50490347464a07fffbad` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R6.md` | `58839fb965e3bd962ed5ffa0914eed6957a8e7097e35f9ccc8d64c2889a6ff64` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R7.md` | `c82ab206d154cdcccf06794e139966724f7a814d4d2201a4fdf27bf3d7cbcb1e` |
| `work/review/REV-0058/WO-0151-RED-CONTRACT-R8.md` | `d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f` |
| `app/execution_core/acquisition.py` | `c757447df8f81545fd2d5a0769d5ce1ad3fa003b567a65f72b006b88eb617f42` |
| `app/execution_core/protection.py` | `54c72282d6b40ed13b5a20f2edfc2144a5d43057783cfe145401ae3419265f39` |
| `app/execution_core/authority.py` | `c79a89c0a6943a30c1fb492d3dddb2489d70d9bcf926cc4b7b19caa6eeda2c3e` |
| `tests/execution_core/test_acquisition.py` | `cf77a7767ff39bad7b3f7f6c1f934356511e40f64ad2c3297ac53cac7f5665f9` |
| `tests/execution_core/test_protection.py` | `28c5af8cd7ed9e64b474fb809e9b9a567e6c623e5098a509de056de559591c1b` |
| `tests/execution_core/test_import_boundary.py` | `236976dae16ce009f826dd558285e192f27fee30eca1259a17319b2fc7e57c82` |

## Findings

No P0, P1, or P2 findings.

The R2--R9 composite preserves one pure controller/fact-applier and the R7
ownership split.  Current source confirms the specific omission: the controller
retains only `scope_protection_commitment`, while an authentic
`AcquisitionProtectionRebaseProjection` retains a sealed predecessor context
commitment rather than the raw predecessor semantic value.  The existing
protection context commitment preimage already binds application generation,
scope, predecessor scope-execution commitment, semantic protection commitment,
and predecessor source-protection commitment.  R9's one owner-side matcher can
therefore prove precisely that missing relation by recomputing that existing
predecessor context commitment, without exposing raw state or reintroducing
authority data into `protection.py`.

R2 already supplies the authority-side registration surface: its sealed
`PROTECTION_REBASE` source and `RegisterAcquisitionCurrentness` path are
separate from the protection projection.  No further R9 authority field,
authority input, registration type, or caller-provided comparison pair is
needed.  The current WIP rebase route remains fail-closed and unimplemented;
that is feasibility context, not accepted implementation evidence.

Static disproof pass:

- A raw source-state commitment or a substituted semantic token does not
  reproduce the predecessor context commitment because the semantic and source
  positions are separately domain-bound in that preimage.
- `None`, a non-`bytes` value, and any non-32-byte value are outside the
  matcher input shape and are non-serving.
- An altered, field-copied, wrong-type, or missing-component projection fails
  the existing protection-owner seal/type/component checks.  A byte-identical
  immutable clone conveys no different relation and still cannot become
  serving authority without the route's current controller/refresh checks.
- `NEUTRAL_REPROJECTION` is disjoint by kind and must return `False`; it remains
  governed only by R7's sealed authority-pair composition.
- An historically authentic projection may answer its narrow predecessor
  relation, but cannot establish currentness: the semantic rebase route still
  requires the retained R6/R7 application-generation, scope, execution,
  venue, fresh authority/venue-context, and raw-protection checks before any
  registration.  A stale prior context is therefore non-serving and
  non-mutating rather than a generic matcher authority.

## Scope and unverified limits

This was an independent static review of the immutable R2+R3+R4+R5+R6+R7+R8+R9
documentation composite, the named ADR/WO/R8 evidence, and the named current
E1 feasibility seams.  Application and test WIP were treated as read-only
context.  No tests, runtime, database, broker, network, or CI work ran; no
implementation behavior, mutation controls, or test results are claimed here.
This result authorizes neither R9 ratification nor implementation.

Verdict: **ACCEPT**

P0: 0
P1: 0
P2: 0
Unverified: Runtime/test execution and any future implementation of the R9-only method and semantic-rebase route were intentionally out of scope.
