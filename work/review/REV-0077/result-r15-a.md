# REV-0077 R15 independent preflight result A

Candidate: `14de501f576b52e128863c9c079f1ba43f13ace4`

Tree: `a896e5ba1468183083af0a659788b0f60797eb18`

Contract SHA-256: `826b733e7b9d7c82dce93e4b712f27ff92c8f6b89590d0ff450994ff42d1626d`

### [P1] The selected owner-rank lookup is not authenticated against source order

- Location: `work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md:20`
- Requirement: R15 lines 20-31 require each direct owner rank to be the immutable insertion ordinal represented by `_owner_order`, while lines 14-15 forbid the projector from walking that order or its radix structure. R15 lines 98-102 require failure-capable controls for the direct route and over-cap noise invariance.
- Evidence (`static-reasoning`): `_owner_order` and `_owner_by_leg` are independent retained structures (`app/execution_core/venue.py:4111-4115`), and the selected SQL owner vector has no source ordinal (`work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md:51-52`). R15 adds another independent map but freezes no pre-existing seal, commitment, inclusion proof, or bounded equality check connecting a selected map value to `_owner_order`. Cardinality and key agreement do not prove ordinal values. The repository already treats `object.__setattr__` corruption of an exact `VenueRecoveryBook` as reachable test input (`tests/execution_core/test_persistence_runtime_checkpoint_pure.py:414-431`); after R15 removes `_validate_full`, swapping two selected owner-rank values remains type-correct, key-complete, and direct-lookup-only. It changes selected owner order and dense wire ordinals while the source-projection commitment merely commits to the forged projection. The listed `missing rank lookup` control does not kill a substituted or swapped rank.
- Impact: A forged or corrupted exact owner can produce authentic-looking checkpoint bytes whose owner source order is not the immutable reducer order. The projector cannot distinguish that state without violating R15's no-scan rule, so the new direct index is not a complete authority substitute for `_owner_order`.
- Resolution: Freeze a bounded authenticated relation between each selected owner and its insertion ordinal (for example, an owner-side authenticated rank witness or independently authoritative durable ordinal), and require substituted/swapped-rank mutants in addition to the missing-rank mutant. The check must remain proportional to selected keys and must not derive its authority from the projection it is validating.

### [P1] The mandatory live-generation wire contradicts the retained nullable selection contract

- Location: `work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md:92`
- Requirement: R15 lines 7-10 retain the recursive R13/R12 authority, and lines 92-94 make every projected controller live-generation member mandatory and reject null as unreachable. The retained R5 SQL contract explicitly admits a present controller whose `live_acquisition_generation_id` is NULL (`work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md:67-72`).
- Evidence (`static-reasoning`): The exact durable record models the live generation as optional (`app/execution_core/persistence/records.py:2549-2558`). The current selection implementation validates every selected scope/controller/protection tuple without rejecting a null controller live ID (`app/execution_core/persistence/repository.py:4578-4614`), then deliberately excludes null IDs when comparing controller LIVE coordinates to selected LIVE generations (`app/execution_core/persistence/repository.py:4672-4684`). Such a scope can therefore enter an authentic selection proof. R15 simultaneously requires a non-null authentic `AcquisitionControllerState` and says its decoder rejects the null form, while line 106 authorizes no SQL/DDL correction and states no selection-proof rejection rule.
- Impact: The repository can select a contract-admitted scope for which no R15 acquisition wire or exact scope owner can exist. Projection must either refuse a valid selected state or silently strengthen the repository contract during implementation, so the frozen checkpoint is not complete or unambiguous at this lifecycle boundary.
- Resolution: Choose and freeze one boundary: either reject every selected null-live controller before proof issuance with an exact outcome and failure-capable control, or define an explicit no-live scope/acquisition candidate and its restart semantics. Reconcile the retained SQL manifest, decoder grammar, projector, and tests in the same reviewed contract.

Fresh non-database evidence: `test_venue_checkpoint_hardening.py` plus `test_persistence_runtime_checkpoint_pure.py` passed (`87 passed`), and `test_persistence_runtime_checkpoint_directness.py` passed (`5 passed`), with bytecode and pytest cache writes disabled.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
Unverified: No SQLite, schema, DDL, query-plan, or database test was run. R15's two proposed rank indexes are documentation-only at the reviewed commit, so their implementation behavior was assessed from the frozen contract and exact current owner/projector source.
