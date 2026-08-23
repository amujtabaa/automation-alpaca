# REV-0077 R16-B independent preflight review

Reviewed exact commit `715d384f76c09ad6b3f959e774cb808a52c2ae64`, tree
`b39f51d93be8ada6abc3fba22a712000b21ced57`, and R16 SHA-256
`5b59d91a99bc707c0d052b84852b4c3332e61476a772c431c918d1576c387de0`.

### [P1] The dormant union drops selected unresolved retired acquisition state

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:59`
- Requirement: R16 admits a selected controller with no LIVE generation and replaces its acquisition component with the nine-member dormant row. The retained R1 acquisition grammar requires `UnresolvedGenerationRows`, `UnresolvedMarketStreamRouteRows`, lineage, and their bounded commitments (`09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md:197-239`); the retained R5 selection contract independently selects `RETIRED_UNSERVING` generations whose unresolved-effect or active-protection count is positive (`16-WO-0168C-R5-SQL-MANIFEST.md:74-122`).
- Evidence (`static-reasoning`): A null `live_acquisition_generation_id` does not exclude Q3b rows. Current selection deliberately compares controller IDs only with the LIVE family, then unions those rows with unresolved retired generations (`app/execution_core/persistence/repository.py:4673-4688`). R16 requires only that the dormant scope have no selected LIVE row (`R16:72`); it neither forbids selected retired rows nor gives the dormant row fields for their registry, route, lineage, or commitments. Its proposed “complete dormant scope matrix” therefore need not fail on this retained valid state.
- Impact: A contract-valid scope with no live generation but one unresolved retired generation must either be rejected despite authentic selection or be encoded without restart-required acquisition semantics. The frozen candidate is not complete for an existing valid lifecycle state.
- Resolution: Define a dormant acquisition candidate that carries and authenticates every selected unresolved retired generation/route/lineage semantic required by the retained R1/R5 contract, or explicitly change the selection boundary to refuse that state. The latter would require separately reviewed SQL/query authority, which R16 currently forbids.

### [P1] `acquisition=None` has no exact owner-preimage representation

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:76`
- Requirement: The recursively retained R6 owner preimage requires each scope row to contain exact byte commitments for acquisition, execution, and protection (`17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md:43-59`). R16 says the supplied scope owner instead contains `acquisition=None`, while retaining the existing owner-preimage boundary.
- Evidence (`static-reasoning`): R16 defines a self-committing dormant wire row but never states that `dormant_commitment` occupies the acquisition source-owner slot, defines a domain-separated absent-owner commitment, or revises `scope_owner_commitments`. The current exact carrier remains `tuple[tuple[int, bytes, bytes, bytes], ...]`, and projection derives the acquisition slot from `acquisition.commitment` (`app/execution_core/persistence/checkpoint_codec.py:100`, `:1637`). `None` cannot satisfy R6's `FIELD_BYTES(acquisition)`. Substituting the dormant row's self-hash would be an unstated integrity commitment, not a commitment authenticated from the absent source owner. The listed dormant controls do not require a wrong-sentinel or owner-preimage-substitution mutant.
- Impact: The implementation has no contract-authorized way to issue a projected envelope for a dormant scope. Any choice either rejects the newly admitted state or silently changes the exact owner-preimage grammar and provenance boundary.
- Resolution: Freeze an exact domain-separated dormant owner commitment, its derivation from the authentic selection proof and dormant row, its position in `scope_owner_commitments`, and failure-capable substitution/omission/cross-scope controls; update the retained R6 formula explicitly.

### [P1] A coherently forged order and rank map still passes for all-dormant selections

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:11`
- Requirement: R16 claims the direct rank lookup is authenticated by the existing source order, that swapped/substituted ranks fail, and that the two derived maps do not alter the existing venue/protection commitment (`R16:11-33`). Projection must remain failure-capable against forged exact owners without a whole-order fold.
- Evidence (`static-reasoning`): For selected IDs `A,B`, replacing source order `[A,B]` with `[B,A]` and rank entries `{A:1,B:0}` preserves exact sizes and makes both `order.get(rank) == key` checks pass. The rank maps are intentionally excluded from `_protection_book_commitment`; the changed order merely produces a new freshly computed venue commitment because that commitment folds dataclass fields including `_effect_order`/`_owner_order` (`app/execution_core/venue.py:7990-8022`). An active acquisition owner would expose the splice through its retained `venue_commitment` comparison (`app/execution_core/persistence/checkpoint_codec.py:1581`), but R16 removes that owner for a dormant scope. Execution and protection owner commitments do not supply the missing expected venue-book commitment, and the projected owner preimage only binds the newly computed value. Thus an all-dormant selected state can authenticate a coherently forged source order and produce different dense selected order while every new R16 rank check passes. The proposed swapped-rank control mutates only ranks and does not require this coherent order-plus-rank negative control.
- Impact: R16 still permits authentic-looking checkpoint bytes whose selected effect/owner order was not the reducer's source order. This defeats the stated purpose of the rank correction precisely on the new dormant path.
- Resolution: Bind selected ranks to an independently retained authentic source-order witness that remains available for dormant scopes, and add coherent order-plus-rank mutants for both effect and owner families under an all-dormant selection. The witness must not be minted from the projection it validates.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 3
P2: 0
Unverified: No SQLite, database, DDL, runtime, or executable test was run. R16 is documentation-only; the three findings are static derivations from the exact candidate, recursive contracts, and current source.
