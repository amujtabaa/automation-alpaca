# M1-to-M2 execution-kernel handoff

Date: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

## Exact identity and authority

- Pure M1 implementation/evidence commit:
  `c148b93bb66cc7d943615337eb4ddf1ab61313ee`.
- Exact Git tree: `0bbe3a0432bb1a62bfa1a5cd849e43d989b5bbaa`.
- WO-0152 R3 manifest SHA-256:
  `ecc85f9ad803080a7a159468be404ecacb60464db0249316fdfba0a962f3ae46`.
- Independent R3 result SHA-256:
  `96680be9a550bf40e48104e12686dfab985866cd76d5c0de6e46519698a2ac9c`,
  verdict `ACCEPT`, P0=0/P1=0/P2=0.
- Accepted architecture authority: ADR-020 R2, ADR-021 R2, and ADR-023 R1,
  with exact ratification provenance in
  `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`.

This handoff freezes pure M1 interfaces and proof. It grants no schema,
database, persistence, runtime, broker, adapter, deployment, or M2 authority.

## External exact-head evidence

GitHub Actions run #771, ID `31291594513`, tested exact SHA
`c148b93bb66cc7d943615337eb4ddf1ab61313ee`.

| Python | Job ID | Conclusion | Tests | Lines | Branches |
| --- | --- | --- | --- | --- | --- |
| 3.11 | `93189636264` | `success` | 5,977 passed; 11 skipped; 1 xfailed | 24,826/26,530 = `93.577083%` | 8,460/9,920 = `85.282258%` |
| 3.12 | `93189636234` | `success` | 5,977 passed; 11 skipped; 1 xfailed | 24,826/26,530 = `93.577083%` | 8,461/9,920 = `85.292339%` |

Both jobs passed Ruff, mypy, all six import contracts, the contamination guard,
AI-OS hygiene, the 61-case R2 oracle, the full suite, and the independently
enforced `93.00%` line and `85.25%` branch ratchets. Run #741 remains retained
functional/static-positive and coverage-negative evidence; it is not
reclassified.

The records-only commit containing this handoff and lifecycle reconciliation
must itself pass exact-head Python 3.11 and 3.12 CI. That external immutable
run is the final M1 effectiveness condition; no recursive evidence-only commit
is required.

## Frozen public M1 surface

M2 consumers use package-root `app.execution_core` exports. They must not
construct sealed values, use private seals or maps, or manufacture authority.

### Identity, mandate, and read surface

- `ApplicationGenerationId`, `AcquisitionGenerationId`,
  `MarketStreamGenerationId`, `PositionScope`;
- `AcquisitionMandate`, `DualMandateBinding`, `ProtectionMandate`,
  `EmergencyRecoveryCompatibility`;
- `GenerationServingClass`, `GenerationRouteKind`, `GenerationBindingView`,
  `GenerationRecordView`, `GenerationRouteView`;
- `GenerationRegistry.record` and `AcquisitionLineageIndex.route_request`,
  `.route_effect`, `.route_owner`, `.route_root`, and `.route_fact`.

### Controller surface and reducers

- `SymbolAcquisitionController`, `AcquisitionControllerState`,
  `AcquisitionControllerStatus`, `AcquisitionControllerTransition`,
  `AcquisitionControllerDisposition`, and `AcquisitionRecoveryClass`;
- `project_acquisition_controller`;
- `initialize_acquisition_controller`, `begin_acquisition_generation`,
  `reduce_acquisition_controller`, `rebase_acquisition_protection`;
- `create_acquisition_effect`, `claim_acquisition_effect`,
  `begin_acquisition_preemption`, and `create_acquisition_protection_exit`.

### Owning reducer boundaries

- `ExecutionSnapshot`, `ExecutionTransition`, and
  `apply_broker_execution_fact`;
- `VenueRecoveryBook`, `VenueRecoveryTransition`, and
  `apply_venue_recovery_input`;
- `ExecutionAuthorityState`, `ExecutionAuthorityTransition`, and
  `apply_execution_authority_input`;
- `PositionProtectionState`, `ProtectionVenueProjection`,
  `ProtectionTransition`, and the exported protection projection/reduction
  functions.

Opaque controller, transition, registry, route, and generation-view values are
reducer-constructed only. M2 must persist authenticated outcomes, not recreate
them from caller-shaped data or treat a projection as authority.

## Pure M1 guarantees

- One exact application-generation and position scope has one bounded
  controller and at most one LIVE acquisition generation.
- A successor is predecessor-linked, advances exact currentness and ordinal,
  uses a distinct market-stream generation, and preserves retired immutable
  ownership.
- Only a first-occurrence canonical `FILL`, or an exact-root immediate-
  predecessor broker-authoritative `TRADE_CORRECT`/`TRADE_BUST`, changes
  position economics.
- A generation-relevant fact yields one composite applied or refused result:
  generation-local economics, aggregate delta, controller currentness,
  protection/recovery, authority/preemption, and effect/claim eligibility do
  not split.
- A retired valid fact updates only its retired direct economics head once. It
  cannot credit successor capacity, restore BUY authority, or create another
  normal controller; a racing final claim refuses before I/O.
- Reducers are deterministic, I/O-free, wall-clock-free, database-free, and
  use direct bounded indexes. Live decisions do not scan or materialize retired
  generations, owners, effects, closures, predecessor chains, or audit history.
- `AcquisitionControllerStatus` is a bounded, authority-free read projection.

## Schema-neutral durable field and projection map

This is a field contract, not DDL.

| Durable relation or projection | Required M1 coordinates |
| --- | --- |
| Controller identity/currentness | application generation, exact position scope, controller head, successor ordinal, live generation, recovery class, execution/venue/authority/protection commitments, controller and compatibility commitments |
| Immutable generation binding | generation ID, application generation, scope, ordinal, dual-mandate binding commitment, predecessor-or-genesis-head commitment, emergency-compatibility commitment, aggregate binding commitment |
| Generation current record | immutable binding, replaceable economics-head commitment, serving class, bounded closure-summary commitment |
| Direct lineage routes | route kind, source commitment, immutable generation ID for request, effect, owner, root, and fact |
| Stream provenance | one distinct `MarketStreamGenerationId` bound to one retained generation binding; no reuse or current-symbol inference |
| Composite checkpoint | exact execution snapshot, venue checkpoint, protection state/commitment, authority currentness/receipt, effect/claim result, and controller state carried by one controller transition |
| Read projection | `AcquisitionControllerStatus` and generation binding/record/route views only; read-only and authority-free |

## M2 atomic persistence boundary

`AcquisitionControllerTransition` is the single pure composite boundary. For
an accepted generation-relevant fact or successor admission, M2 must make one
SQLite unit of work durably old-or-new for:

- accepted fact/revision and execution-chain head;
- aggregate execution checkpoint and exact generation economics head;
- request/effect/owner/root/fact-to-generation routes;
- controller currentness and generation registry;
- venue closure/effect/claim state;
- protection state and authority receipt; and
- the composite decision receipt.

M2 must never durably expose two LIVE generations, an accepted root without an
immutable generation binding, or a successor without predecessor,
compatibility, stream-provenance, and currentness proof. A refusal or replay
must not become a partial write.

## Evidence carried forward

- E1 retained deterministic identity known answers, replay/coordinate-change,
  direct-lineage routing, and authority-free projection controls.
- E2 retained its pure execution-core suite, focused fact/mutation controls,
  and named fail/restore mutations over compatibility, one-LIVE uniqueness,
  controller-head advance, exactly-once aggregate application, currentness,
  capacity isolation, and final-claim revalidation.
- E3 retained public 32-generation serial and rooted retired-fact lanes,
  seeded state-machine and schema-neutral replay/restart observer equivalence,
  corruption/reordering refusals, sixteen history-materialization tripwires,
  exact source-policy controls, and decisive omission/false-value mutants.
- The R13 successor B first-fill detector passed unchanged before E3 resumed.
- WO-0152 contains no application production-code change.

## Explicitly deferred

- M2: reviewed SQLite schema and constraints, DDL, serialization, atomic
  persistence, crash old-or-new behavior, startup validation, durable receipts,
  and recovery.
- M4: broker/adapter fact correlation to immutable generation/root/effect/owner
  routes. No broker permission follows from M1.
- M7/M8: controller observation and UI/API projection integration. Status
  projections confer no authority.
- Runtime: process ownership, dispatch, restart/reconnect, configuration,
  cutover, and operational wiring.
- Database, migration, broker/network/Alpaca activity, credentials, master
  landing, merge, PR, and branch retirement.

The handoff is not M2 activation and is not an operational-readiness claim.
