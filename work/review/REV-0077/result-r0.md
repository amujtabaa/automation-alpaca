# REV-0077 independent review result R0

- Candidate: `d6319e556f1446f26d6dd2f8eb87f602dd75004e`
- Tree: `84ce45ff78768071e645fba8b7e54b10acce7f27`

### [P1] Checkpoint issuance is circular

- Location: `work/queue/M2-EXECUTION-2026-08-21/08-WO-0168C-FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:93`, `:99`, `:127`, `:170`
- Evidence level: `static-reasoning`
- Evidence: `encode_runtime_checkpoint` requires a matching repository proof bundle, but `load_checkpoint_proof` issues that bundle only after finding the matching `kernel_checkpoint` and immutable payload. Persistence simultaneously requires encoding/storing the payload before advancing that head.
- Impact: A new checkpoint cannot be encoded through the specified authority path without either using a caller-shaped pre-persistence substitute or bypassing the required bundle.
- Root resolution: Define separate repository-issued pre-persistence observation authority and post-persistence serving authority, with exact coordinates and an acyclic issuance sequence.

### [P1] A sealed historical bundle can remain serving after its head becomes stale

- Location: `...FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:94`, `:111`, `:138`, `:145`
- Evidence level: `static-reasoning`
- Evidence: The compositor accepts only `(inert_envelope, authentic_checkpoint_proof_bundle)`. It has no connection, transaction-lifetime token, current-head capability, or other fact with which to determine that the repository head has advanced since bundle issuance. A seal proves provenance, not present currentness.
- Impact: An authentic old payload and bundle can compose serving owners after replacement by a newer checkpoint, defeating stale-proof refusal.
- Root resolution: Bind composition to the still-open repository snapshot or introduce a repository-issued, non-escaping current-head capability consumed and revalidated at composition.

### [P1] Execution and protection serving-proof issuance is not closed

- Location: `...FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:42`, `:138`, `:140`, `:164`
- Evidence level: `static-reasoning`
- Evidence: Proof bytes are correctly excluded, but the replacement proof coordinates and issuer seams are unspecified. Existing execution issuance requires an authentic `ExecutionSnapshot` and four `_PersistentKeyMapWitness` objects (`app/execution_core/position.py:596`), while the proposed bundle defines no exact witness members or repository-only constructor. The named protection route consumes `CurrentProofSlice`, but the contract does not define how a `CheckpointProofBundle` issues authentic per-scope slices.
- Impact: Implementation must invent a proof format or constructor. A permissive implementation can let repository-shaped or caller-shaped data mint serving proof types; a strict implementation cannot hydrate execution/protection.
- Root resolution: Freeze every witness row, absence coordinate, bundle-to-proof constructor input, issuer identity, and exact per-scope proof conversion before source work.

### [P1] The bounded snapshots cannot reproduce unchanged serving-owner commitments

- Location: `...FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:27`, `:145`, `:153`
- Evidence level: `static-reasoning`
- Evidence: The incorporated acquisition wire explicitly states that its bounded commitments are not the existing history-shaped `AcquisitionControllerState.commitment` and cannot participate in reduction without a separately frozen behavioral commitment (`07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:826-838`). Current source commits the complete registry and lineage seals (`app/execution_core/acquisition.py:2105-2109`). Venue and authority snapshots likewise omit direct/history state.
- Impact: Byte-for-byte re-encoding proves only equality of the lossy snapshot projection. Different serving owners can re-encode identically while retaining different replay, deduplication, lineage, or reducer behavior.
- Root resolution: Either make the representation injective over every serving member and existing commitment, or keep it non-serving and define a separately reviewed behavioral-state authority without claiming unchanged owner reconstruction.

### [P1] The unchanged DDL cannot prove the required late-owner selection with bounded work

- Location: `...FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:104`, `:115`, `:120`, `:176`
- Evidence level: `static-reasoning`
- Evidence: Selection includes effects whose disposition is not `CLOSED` or which have a late owner. The DDL indexes effects by `(scope_id, disposition, effect_id)` but indexes owners by `(effect_id, admitted_after_effect_closed, scope_id, …)` (`app/execution_core/persistence/schema.py:669`, `:712`). There is no index beginning with scope/late-admission. Finding closed effects with late owners therefore requires traversing closed effect history or scanning the owner index.
- Impact: Work grows with unrelated terminal history, contradicting the bounded-state and indexed-search requirements.
- Root resolution: Add and human-gate an index supporting the exact late-owner predicate, or redesign and freeze a genuinely bounded direct key. The claim that no additional DDL is needed is not supported.

### [P1] The contract excludes the commitment grammar it depends on

- Location: `...FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md:32`, `:88`, `:108`
- Evidence level: `static-reasoning`
- Evidence: The closed annex incorporates sections 2.1–2.4 but excludes section 2.5, which defines `K(domain,row)`, self-commitment omission, count-wrapper coverage, domains, and the acyclic dependency order (`07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:200-229`). The candidate nevertheless requires every inner and family commitment to be re-derived.
- Impact: Multiple incompatible commitment implementations satisfy the surviving prose, weakening splice detection and preventing one canonical implementation.
- Root resolution: Incorporate the exact retained commitment construction and dependency graph, explicitly removing only the superseded transition-proof domains.

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 6
P2: 0

Unverified:

- No SQLite command, query plan, or SQLite-bearing test was run.
- Full implementation/test coverage was not inspected after the instruction to conclude.
- Working `HEAD` is `94e0321c15d2f90d837de779b10778551f0a6519`; review used immutable candidate `d6319e556f1446f26d6dd2f8eb87f602dd75004e`.
- Candidate identity, parent, tree `84ce45ff78768071e645fba8b7e54b10acce7f27`, annex hash, and static DDL `178,011` bytes / SHA-256 `0460ac5a69d35684ad1ac4ee6571b1a7f04824ed936e0998dac4db645f95544a` were verified without SQLite.
