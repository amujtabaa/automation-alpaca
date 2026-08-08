# Complexity ledger — serial acquisition generations

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

The ledger is deliberately narrow. Every item below must trace to a named failure in REV-0054 or
to a roadmap obligation; no item is speculative extensibility.

| Addition | Why it is necessary | Bounded shape and invariant | Not introduced |
|---|---|---|---|
| AcquisitionGenerationId | Distinguishes A from B/C without overloading deployment or market identities. | Reducer-minted once, immutable, one scope/binding/ordinal; never caller-shaped. | Random caller IDs, global campaign service. |
| GenerationRecord | A terminal A must retain immutable ownership yet accept valid correction/bust economics. | Direct key to immutable provenance plus one replaceable linked economics head; status LIVE or RETIRED_UNSERVING. | Mutable tombstone, predecessor-chain walk, reopened BUY authority. |
| Direct generation registry / root-effect-owner index | A late root must resolve A after B/C without searching history. | Direct indexed lookup; every valid root maps to exactly one generation; missing/ambiguous mapping is non-serving. | Audit scan, list materialization in a live transition. |
| Per-generation closure summary | Admission needs exact bounded evidence that A cannot still execute. | Current counters/heads for relevant ownership, acceptance, reconciliation, and terminal proof. | Re-enumeration of all historical effects/legs. |
| SymbolAcquisitionController | Existing single scope head cannot represent current B plus retired A economics. | One bounded scope record, one aggregate, one currentness head, at most one LIVE generation, one active protection authority; no retired-generation collection. | Multiple controllers, concurrent generations, second writer. |
| AcquisitionLineageRelation | M1D must distinguish B's first root from a late A root without trusting a caller. | Opaque reducer-derived projection sealed to source root/effect, generation, venue/execution commitments, and controller head. | Public constructor, test seam, private venue accessor. |
| EmergencyRecoveryCompatibility | Distinct normal mandates otherwise leave no authority to take one safe response to old+A/B aggregate exposure. | Immutable equality commitment: scope/session, emergency guard/rate/deadline, aggregate emergency cap, compatibility ID. Set once at controller genesis and never replaced; successors prove exact equality. | General policy merger, normal-trail composition, per-generation exit controller. |
| MIXED_GENERATION_RECOVERY classifier | A late retired fact must be conservative without making B's normal first fill self-preempt. | One controller-level restricted hard-bail state; no new entry, aggregate protection only, at most one action eligibility. | Automatic allocation of quantity/basis between policies. |
| Controller-head binding on create/claim | A late A update must invalidate B work already created but not claimed. | Creation and final claim include exact generation plus controller head; stale equality fails closed. | Post-claim recall, double cancel route. |

## Complexity budget and asymptotics

- Live transition lookup remains constant-sized: controller-by-scope, generation-by-ID,
  root/effect/owner-to-generation, and closure-summary lookup are direct indexes.
- Durable lineage grows with retained canonical facts/generations because corrections remain valid;
  this is unavoidable evidence, not live reducer state. The bounded controller holds pointers and
  summaries, never a historical collection.
- The design adds no new process, database, service, queue, event log, runtime actor, or policy
  interpreter. M2 persistence work is specified only as a future atomic extension of existing
  state/fact/effect ownership.
- If a requirement needs two active generations, different emergency compatibility, market-stream
  reuse, or automatic policy combination, it exceeds this ledger and requires another ADR.

## Why smaller alternatives are insufficient

A one-time "never used" bit cannot support M6 repeat acquisition. A single immutable tombstone
cannot advance A's economics after a correction. Reusing A's FLAT protection state makes B
look late; resetting it loses A's provenance. The controller, direct lineage head, and sealed
relation are therefore the minimum root-level correction rather than patches around those errors.
