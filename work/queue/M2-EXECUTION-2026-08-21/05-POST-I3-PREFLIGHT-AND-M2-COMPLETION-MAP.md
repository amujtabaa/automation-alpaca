# Post-I3 preflight and remaining M2 completion map

Status: **PREFLIGHT REMEDIATION CANDIDATE — DOCUMENTATION ONLY — SOURCE IMPLEMENTATION HELD**

Date: 2026-08-22

Exact predecessor: WO-0167 closeout commit
`0777fab62598f85ce189f40eb1a69319791282c2`, tree
`1db6fe831fc7d7785d032c224072b131cd5643e9`.

This additive record preserves the manifest-bound 2026-08-21 preparation packet unchanged. It
supersedes that packet's live status assumptions only where the accepted WO-0165 through WO-0167
implementation now supplies better evidence.

## Outcome-first summary

M2 still has three planned implementation outcomes after I3: atomic transitions, fail-closed
startup/recovery, and fault/restore closeout. The first cannot safely start from the current
WO-0168 text. Two independent clean-context preflight reviewers found the same root gap:

1. the accepted schema has no durable input/outcome or mandatory decision-receipt authority;
2. the checkpoint stores a digest but no bounded canonical representation from which the existing
   opaque pure reducer state can be authenticated and reconstructed;
3. WO-0168 does not freeze a finite input-to-reducer-to-write-set matrix or the exact transaction
   and commit-ambiguity protocol; and
4. public repository mutators are not yet structurally restricted to the future unit of work.

Implementing around those gaps would either invent a second engine, pass caller-shaped authority,
or make an unauthorized schema change. The root correction is one prerequisite implementation
increment, WO-0168a. It does not weaken or replace the ratified M2-I4 semantics.

The first formal reviewer preserved that stop as `REV-0074/result.md` (P0=0/P1=1): the initial
candidate correctly required a finite matrix but had not frozen it. The additive
`06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md` now supplies the exact operation union, state
inventory, encoding, schema, capability, path, budget, and fault contract. Source remains held
until a fresh head-bound review accepts that remediation with P0=0/P1=0.

R1 preserved one adjacent P1: primary input identity could not substitute for query/grant and other
alternate semantic-key history. The R2 candidate adds one exact immutable semantic-key family and
owner-proof mapping; source remains held pending fresh acceptance.

## Remaining serial chain

| Order | State after this preflight candidate | Purpose | Exit required before successor |
| --- | --- | --- | --- |
| WO-0165 / M2-I1 | `CLOSED` | Durable values/profile codecs | Accepted exact head retained |
| WO-0166 / M2-I2 | `CLOSED` | Schema/direct proof foundation | Accepted exact DDL retained |
| WO-0167 / M2-I3 | `CLOSED` | Typed direct repository projections | REV-0073 R5 ACCEPT retained |
| WO-0168a / M2-I3.5 | `READY-PREFLIGHT` | Bounded canonical runtime-state hydration plus durable input/outcome/receipt substrate | Exact state/input matrix, independently accepted implementation, and any changed DDL separately human-gated before execution |
| WO-0168b / M2-I4 | `PREPARED-BLOCKED` | Atomic reducer/unit-of-work and post-commit effect eligibility | WO-0168a accepted; regenerated exact work order and independent P0=0/P1=0 review |
| WO-0169 / M2-I5 | `READY-BLOCKED` | Owner lock, startup, reconciliation, ADR-023 cold recovery | WO-0168b accepted and activation reconciliation passes |
| WO-0170 / M2-I6 | `READY-BLOCKED` | Fault, restore, boundedness, soak/R16 truth, M2 closeout | WO-0169 accepted and activation reconciliation passes |
| WO-0171 / M3-P1 | `PREPARED-BLOCKED-BY-M2` | Deterministic simulator/tape/clock | Exact M2 closeout plus separate M3 activation |
| WO-0172 / M3-P2 | `PREPARED-BLOCKED-BY-M2-AND-P1` | Semantic comparator and permanent regression corpus | Accepted M3-P1 plus separate activation |

The historical `work/queue/WO-0168-m2-i4-atomic-unit-of-work-effects.md` remains unchanged as
manifest-bound planning evidence. It is not activation authority. WO-0168b will regenerate its
exact executable successor contract from the accepted WO-0168a interface rather than silently
editing the historical packet.

## Mandatory checkpoint order

```text
REV-0074 remediation preflight acceptance
  -> WO-0168a runtime-state/input-receipt substrate
  -> fresh implementation review
  -> WO-0168b atomic unit of work/effect eligibility
  -> fresh implementation review
  -> WO-0169 startup/reconciliation/cold recovery
  -> fresh implementation review
  -> WO-0170 fault/restore/boundedness closeout
  -> fresh terminal M2 review and M3-entry handoff
```

No implementation result may activate its successor until a clean-context reviewer returns
P0=0/P1=0 for the exact candidate head. A reviewer result is evidence, not permission to merge to
`master`.

## Revised M2 completion proof

In addition to the original definition of M2 complete, the final candidate must prove:

- one finite, exact input-to-owning-reducer-to-durable-write mapping;
- one bounded, canonical, independently validated runtime-state representation that reconstructs
  authentic reducer state without replaying audit history or using pickle/repr/reflection;
- durable immutable input identity/payload/outcome and mandatory non-authoritative decision
  receipts, atomically bound to the same checkpoint transition;
- a unit-of-work-only runtime write capability while direct repository mutators remain test/setup
  infrastructure;
- exact `BEGIN IMMEDIATE`, rollback, commit, commit-return ambiguity, cache publication, and
  post-commit eligibility semantics; and
- startup reconstruction from accepted direct proof, not a caller-supplied supposedly current
  object.

## Preflight authority and stop boundary

Ameen Mujtabaa's 2026-08-22 request authorizes mapping, preflight, consecutive ordinary reversible
M2 implementation, governance records, branch publication, and clean-context review pauses. It
does not silently approve a new exact DDL identity. Static DDL candidate authoring is permitted;
executing changed DDL or schema tests requires the repository's exact human gate unless a current
record explicitly covers those exact bytes and test plan.

No configured or existing database, migration, credentials, broker/network call, order, runtime
composition, promotion, implementation-branch merge to `master`, destructive branch operation, or
M3 implementation is authorized by this record.
