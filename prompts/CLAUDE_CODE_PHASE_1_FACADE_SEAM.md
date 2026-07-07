# Claude Code Handoff — Phase 1 Facade Seam Only

## Preconditions

Do not use this prompt until Phase 0 is complete and reviewed.

Read:

1. root `CLAUDE.md`
2. `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`
3. `docs/adr/ADR-005-api-facade-boundaries.md`
4. `docs/SPINE_PHASE0_INVENTORY.md`
5. `docs/SPINE_PHASE0_MIGRATION_PLAN.md`

## Goal

`/goal Phase 1A-1C: create the API facade migration seam without changing production trading behavior.`

This phase creates the seam that will later allow the execution spine to migrate safely. It does not implement event sourcing, timeout quarantine, overfill quarantine, or new manual-flatten semantics.

## Allowed

- Add command/query facade protocols.
- Add facade DTOs and command/query objects.
- Add domain error classes and HTTP mapping skeleton.
- Wrap existing behavior behind facade methods.
- Refactor one low-risk read-only route to use `QueryFacade` if behavior is unchanged.
- Refactor one low-risk command route to use `ExecutionCommandFacade` if behavior is unchanged.
- Add characterization tests showing behavior did not change.
- Add boundary tests for the migrated route(s).

## Not allowed

- No event-log-as-truth implementation.
- No rewrite of order/fill/position semantics.
- No timeout-quarantine behavior change.
- No overfill-quarantine behavior change.
- No manual-flatten policy change.
- No adapter behavior change.
- No live-trading path.

## Tasks

1. Add facade package skeleton if not already present:
   - `app/facade/__init__.py`
   - `app/facade/protocols.py`
   - `app/facade/commands.py`
   - `app/facade/queries.py`
   - `app/facade/errors.py`
   - `app/facade/http_mapping.py`
2. Add FastAPI dependency providers for the facade.
3. Choose one low-risk read-only route and wrap it through the query facade.
4. Choose one low-risk command route and wrap it through the command facade, with no behavior change.
5. Add tests proving the route behavior is unchanged.
6. Add boundary tests or import-linter dry-run documentation showing remaining violations.
7. Run tests.
8. Update `docs/SPINE_PHASE1_FACADE_REPORT.md`.

## Output required

`docs/SPINE_PHASE1_FACADE_REPORT.md` must include:

- changed files;
- routes migrated;
- behavior-equivalence evidence;
- remaining direct API dependencies;
- tests run;
- failures/blockers;
- recommended next phase.

## Stop condition

Stop after Phase 1 facade seam. Do not start event sourcing or execution behavior migration.
