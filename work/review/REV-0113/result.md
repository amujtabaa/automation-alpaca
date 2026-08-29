# REV-0113 — Independent executable-contract preflight

## Verified target

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Accepted predecessor: `25aca36956d68db014df3769678699597e9be56a`, tree `aa79bee93b51b81d4b004a154f86cc7ca547d17f`.
- Contract candidate: `9485256811e633578c0059afe15b160c4555d8b6`, tree `f31bed27f8041550f78c81f6dc502e8b28bf523f`, with the accepted predecessor as its exact parent.
- The workspace packet overlay is at `b408edec9dbfd8474a12d4603d90c7f96f1e9230`; the candidate is its ancestor, and the only tracked post-candidate changes are `work/ledger.jsonl` and `work/review/REV-0113/request.md`. All reviewed code and companion-contract files are therefore byte-identical to the exact candidate.
- Active work-order SHA-256: `bcc99128c68cb4784b83b9c13b597f77745cce30acf71aab59e53777d48f04a9`.
- Frozen schema blob is unchanged from predecessor to candidate at `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`. Static AST extraction of `SCHEMA_DDL` produced exactly 180,858 UTF-8 bytes and SHA-256 `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact `False`. The flag-true execution commit is confined to `codex/m2-wo0168d-ddl-execution-r4` and is not an ancestor of the contract candidate.
- Candidate scope is exactly the new active work order plus one append-only ledger row; `git diff --check 25aca36956d68db014df3769678699597e9be56a 9485256811e633578c0059afe15b160c4555d8b6` passed.

### [P1] The bounded checkpoint omits manual state that admitted reducers still read

- Location: `work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md:87`
- Requirement: The frozen boundary and FR-1 require every caller-owned owner state member that can affect reduction to be authenticated against direct proof before the reducer runs. Companion contract 06 further says `AdvanceManualFlatten` uses the retained semantic key and the active manual state; omitted terminal history must not become current authority.
- Evidence (`reproduced-live`, pure/no-database): `checkpoint_codec._encode_runtime_checkpoint_manual_rows` deliberately omits `_manual_by_id` entries not reached through `_manual_flatten_by_scope` (`app/execution_core/persistence/checkpoint_codec.py:4292`), and the accepted pure control pins byte-identical payloads when such an entry is added. However, `_begin_manual_flatten` checks `_manual_by_id` directly before the active scope index (`app/execution_core/authority.py:9558`), and `_advance_manual_flatten` also reads `_manual_by_id` directly (`app/execution_core/authority.py:9650`). Using the existing pure `_manual_projection_inputs` fixture, an exact `ExecutionAuthorityState` with one added omitted `_manual_by_id` row passed `_project_runtime_checkpoint` and produced bytes identical to the clean state. With an exact fresh `BeginManualFlatten` input and a fresh manual semantic identity, the clean state returned `REFUSED:VENUE_UNCERTAIN` while the payload-identical altered state returned `CONFLICT`. A second exact `AdvanceManualFlatten` probe returned `REFUSED:MANUAL_FLATTEN_INVALID` for the clean state and `APPLIED` for the payload-identical altered state. No proxy, subclass, database, or alternate reducer was involved.
- Disproof: Primary replay cannot explain either difference because both probes used fresh `AuthorityInputId` values. The stronger `BeginManualFlatten` probe also used a fresh `ManualFlattenId`, so an absent retained semantic key is the expected C3/C4 fact for both contexts and cannot distinguish them. Exact type checks do not distinguish them because `ExecutionAuthorityState` has no aggregate authenticity seal and `_validate_authority_state` shape-checks the persistent maps. The accepted projector intentionally treats the added row as omitted noise. The provisional finding therefore survives the current direct-proof, projector, primary-identity, and semantic-key controls.
- Impact: The contract can commit a durable owner disposition, receipt, and outcome selected by unauthenticated caller-owned state even though the direct proof and canonical checkpoint projection are identical. The `AdvanceManualFlatten` case is stronger: an `APPLIED` owner result can mutate only omitted authority history and the omitted input ledger, so C7 can classify the projection as no-change and return a successor context containing state that was never checkpoint-authenticated. This contradicts FR-1 and the old-complete/new-complete boundary in FR-2.
- Resolution: Add an explicit operation-keyed owner-authentication seam at the authority boundary before implementation. For manual operations, bind the exact `_manual_by_id[flatten_id]` value either to the active `_manual_flatten_by_scope` row represented by the current checkpoint or to the retained semantic/durable-input evidence used for terminal history, and ensure the public reducer cannot consult an unbound omitted row. Pin both payload-equal counterexamples so adding, removing, or changing an omitted manual row cannot alter the reducer result. Serializing the entire historical map is not required; the correction should authenticate the exact member the selected operation can read.

## Executed evidence and limits

- Focused pure suites passed at 100%: `tests/execution_core/test_persistence_operations.py` (50), `tests/execution_core/test_persistence_runtime_checkpoint_pure.py` (162), and `tests/execution_core/test_persistence_write_capability.py` (6), for 218 collected tests.
- The failure-capable manual-state probes above reproduced outside the existing assertions and survived the refutation checks.
- No SQLite connection, database creation/access, DDL installation/execution, migration, configured or in-memory database, credential load, broker/network call, order, runtime composition, or held-suite execution occurred.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: SQLite/database/DDL/held-suite runtime behavior was not executed because the packet prohibits it.
