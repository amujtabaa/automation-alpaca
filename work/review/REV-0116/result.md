### [P1] Cold startup cannot construct or retry its required request safely

- Location: [WO-0169](G:/dev-hdd/automation-alpaca/work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md:123)
- Requirement: Cold restart must acquire ownership before database access, hydrate from direct proof, and remain retryable after fail-closed outcomes.
- Evidence (`static-reasoning`): `StartupRequest` requires a live [UnitOfWorkContext](G:/dev-hdd/automation-alpaca/app/execution_core/persistence/unit_of_work.py:89), while persisted checkpoints load as explicitly inert [RuntimeCheckpointEnvelope](G:/dev-hdd/automation-alpaca/app/execution_core/persistence/checkpoint_codec.py:119). After invalidation commits successor context C1, a later source refusal returns `NON_SERVING` without C1. Retrying with original C0 fails as stale; obtaining C1 first requires the database access the coordinator is supposed to owner-gate.
- Impact: A normal invalidation-then-refusal path can permanently dead-end cold recovery or force pre-lock database hydration.
- Resolution: Make `StartupRequest` carry only immutable startup-selection coordinates. Acquire ownership, load and hydrate the current `UnitOfWorkContext` internally, and keep it private until `SERVING`. Add an invalidation-commit/source-refusal/retry control.

### [P1] Reconciliation omits current unresolved effects outside literal `OPEN`

- Location: [WO-0169](G:/dev-hdd/automation-alpaca/work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md:165)
- Requirement: FR-4 and CR-09/CR-10 require complete targeted reconciliation of every claimed unresolved effect.
- Evidence (`static-reasoning`): [load_open_venue_effects](G:/dev-hdd/automation-alpaca/app/execution_core/persistence/repository.py:3551) selects only `disposition = 'OPEN'`. The authenticated checkpoint selection includes `OPEN`, `INVALIDATED`, and qualifying closed-late-owner effects, and checks that this complete union equals retained unresolved counters ([repository.py](G:/dev-hdd/automation-alpaca/app/execution_core/persistence/repository.py:4177), [repository.py](G:/dev-hdd/automation-alpaca/app/execution_core/persistence/repository.py:5050)). A claimed `INVALIDATED` effect with unknown outcome is therefore skipped.
- Impact: Startup either remains non-serving forever when final proof detects the unresolved effect, or incorrectly declares incomplete coverage complete.
- Resolution: Define reconciliation over the complete authenticated current-unresolved union, including qualifying invalidated and closed-late-owner cases, while querying only exact claimed identities.

### [P1] Final serving transition does not prove the subscription remains current

- Location: [WO-0169](G:/dev-hdd/automation-alpaca/work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md:176)
- Requirement: FR-6/FR-7 and CR-19 require stream loss to remain non-serving.
- Evidence (`static-reasoning`): After baseline commit, step 10 revalidates only database proof and the owner lease. The market-source port has no specified currentness role. A source can lose the acknowledged subscription after returning the baseline but before step 10; all stated final checks still pass and startup returns `SERVING`.
- Impact: Startup can publish serving state without the subscription needed for authoritative post-fence `>F` work.
- Resolution: Add exact subscription-currentness evidence bound to the acknowledgement, fence, source, generation, and mode; revalidate it immediately before `SERVING`. Pin the post-baseline/pre-return loss window with a failure-capable control.

```text
Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 3
P2: 0
Unverified: NONE
```

