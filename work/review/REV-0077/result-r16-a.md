# REV-0077 R16-A independent preflight review

Reviewed exact commit `715d384f76c09ad6b3f959e774cb808a52c2ae64`, tree
`b39f51d93be8ada6abc3fba22a712000b21ced57`, and R16 SHA-256
`5b59d91a99bc707c0d052b84852b4c3332e61476a772c431c918d1576c387de0`.

### [P1] The dormant union drops selected unresolved acquisition state

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:59`
- Requirement: The recursively incorporated acquisition contract requires every selected retired unresolved generation, stream route, and standing lineage route to remain in the bounded acquisition component (`work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:749`, `:804`, `:865`). Repository selection deliberately admits those `RETIRED_UNSERVING` rows independently of whether the controller has a LIVE generation (`work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md:154`).
- Evidence: `static-reasoning` — R16 lines 59-85 makes every null-LIVE scope use one fixed controller-derived dormant row and removes its `AcquisitionControllerState`, but it forbids only a selected LIVE generation. The retained selection model stores unresolved generations/current rows as independent proof families (`app/execution_core/persistence/records.py:666-673`), and the repository unions them into selected generation state regardless of `controller_live` (`app/execution_core/persistence/repository.py:4672-4698`). Therefore an authentic scope with `live_acquisition_generation_id=None` and one unresolved retired generation is selected, while the dormant row has no generation, stream-route, or lineage members with which to encode or authenticate that selected state.
- Impact: The projector must either omit repository-selected restart-required acquisition semantics, reject a contract-admitted selection, or silently place those semantics outside the closed acquisition union. The candidate is not complete for a valid nullable-controller lifecycle state.
- Resolution: Freeze a dormant acquisition form that carries and authenticates the exact selected unresolved registry/lineage subset, or explicitly exclude null-LIVE scopes with unresolved selected generations through a reconciled selection rule. Add a failure-capable null-LIVE plus unresolved-retired-generation control.

### [P1] Dormant protection and execution owners lack a complete cross-binding rule

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:72`
- Requirement: Projection must reject stale or spliced source owners, and the selected controller/protection rows must authenticate the exact inert execution and protection components. The existing protection reconstruction relation checks the protection state's scope, stream, mandate, session, sequence mode, and state commitment against repository authority (`app/execution_core/protection.py:2805-2819`), while the selected null-active authority cannot use that active proof shape (`app/execution_core/protection.py:2678-2699`).
- Evidence: `static-reasoning` — R16 requires only that controller aggregate quantity and selected scope coordinates agree with the execution owner. It does not require `controller.integrity_state` to agree with the execution component, `protection.raw_quantity` to equal execution quantity, `protection.execution_commitment` to equal `execution.commitment`, or `protection.commitment.hex()` to equal the selected `ProtectionAuthorityRecord.state_commitment_sha256`. The current projector demonstrates that execution and protection are independently authenticatable objects (`app/execution_core/persistence/checkpoint_codec.py:1556-1564`), and its only cross-owner commitment checks flow through the acquisition owner (`app/execution_core/persistence/checkpoint_codec.py:1579-1587`), which R16 removes for the dormant branch. A same-scope stale protection owner and a different authentic execution owner with the same quantity therefore satisfy the stated dormant checks.
- Impact: A projected payload can bind individually authentic but mutually inconsistent execution/protection state to a valid dormant controller row. Its owner preimage then authenticates the splice instead of detecting it, undermining exact source-owner provenance before persistence.
- Resolution: Freeze the complete dormant relation explicitly: controller quantity/integrity to execution, protection scope/raw quantity/execution commitment to execution, and selected protection state commitment/version/head to the exact protection component and controller. Add one independently failing same-scope stale-protection mutant for each relation.

### [P1] The superset controls are not failure-capable per authority family

- Location: `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:47`
- Requirement: R16 classifies `_effect_authority_by_id`, `_claim_by_effect`, `_claim_by_occurrence`, and `_acquisition_descriptor_by_effect` separately as authenticated supersets, so the controls must disprove whole-map completeness for each family rather than only for the authorization map.
- Evidence: `static-reasoning` — the only exact noise case at lines 53-55 adds unselected closed ownerless authorizations. It does not add an unselected historical claim or acquisition descriptor. Those maps are independently inserted and retained (`app/execution_core/authority.py:8190`, `:8512-8518`, `:9456-9460`). A projector mutant that correctly subsets `_effect_authority_by_id` but compares reached claims or descriptors with that map's whole size passes the specified authorization-noise case while rejecting an authentic state containing unrelated retained history in that family. The generic controls at lines 89-93 do not name a distinct per-family counterexample or mutant.
- Impact: The R15 whole-map-cardinality defect can survive selectively in three of the four newly classified superset families, making checkpoint availability depend on unrelated authority history despite the stated per-family rule.
- Resolution: Add separate noise-invariance fixtures and family-local whole-cardinality mutants for effect authorization, both claim indexes as one consistency pair, and descriptor-by-effect. Each fixture must hold the selected payload fixed while adding only unrelated history in the targeted family.

Unverified: No SQLite, DDL, schema, database, runtime-composition, or serving-path test was run. The focused pure venue/checkpoint/directness command exited successfully with bytecode and pytest cache writes disabled; it predates R16 implementation and does not exercise these documentation-only obligations.

P0: 0
P1: 3
P2: 0
Verdict: ACCEPT-WITH-CHANGES
