# Claude Code Handoff — Phase 0 Spine v2 Setup Only

## Goal

`/goal Phase 0 Spine v2 setup only.`

This is a setup, inventory, harness, and characterization pass. Do **not** rewrite the execution engine. Do **not** change production trading behavior. Do **not** migrate order/fill/position semantics yet.

## Read first

Read the root `CLAUDE.md` first and treat it as the controlling operating contract.

Then read, in order:

1. `docs/00_START_HERE_SPINE_UPGRADE.md`
2. `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`
3. `docs/SPINE_V2_ACCEPTED_DECISIONS_ADDENDUM.md`
4. `docs/MIGRATION_MATRIX.md`
5. `docs/REARCHITECTURE_ROADMAP.md`
6. `docs/adr/ADR-001-overfill-quarantine.md`
7. `docs/adr/ADR-002-timeout-quarantine.md`
8. `docs/adr/ADR-003-manual-flatten-halted-reducing.md`
9. `docs/adr/ADR-004-event-log-truth-migration.md`
10. `docs/adr/ADR-005-api-facade-boundaries.md`
11. `docs/STALE_ARTIFACT_CLEANUP_GUIDE.md`

If any required file is missing, stop and report the missing file. Do not invent missing architecture.

## Scope

Allowed:

- Inventory current repo architecture.
- Confirm stale implementation prompts are archived and non-binding.
- Add non-invasive harness/check scripts if missing.
- Add facade protocol skeletons only if they do not change behavior.
- Add characterization tests around existing behavior.
- Add documentation describing direct API/store/broker/monitoring dependencies.
- Run pytest collection and the current suite if feasible.

Not allowed:

- No execution-engine rewrite.
- No event-sourced store implementation.
- No timeout-quarantine behavior change.
- No overfill-quarantine behavior change.
- No manual-flatten / kill-switch behavior change.
- No adapter behavior change.
- No production trading behavior change.
- No live-trading path.

## Tasks

1. Verify `CLAUDE.md` imports resolve.
2. Inventory package/module boundaries:
   - UI dependencies.
   - FastAPI route dependencies.
   - Store mutation paths.
   - Broker/Alpaca imports.
   - Monitoring loop mutation paths.
3. Identify direct API → store/broker/monitoring dependencies.
4. Identify where current behavior conflicts with accepted ADRs, without changing the behavior yet.
5. Add or update characterization tests for the current behavior most likely to be changed later:
   - manual flatten behavior;
   - stale/submitting retry behavior;
   - broker-reported overfill behavior;
   - fill/position derivation behavior;
   - kill switch/session behavior.
6. If safe, add facade protocol skeletons only:
   - `app/facade/protocols.py`
   - `app/facade/commands.py`
   - `app/facade/queries.py`
   - `app/facade/errors.py`
   These should be inert definitions unless an existing low-risk route can be wrapped with no behavior change.
7. Run:
   - `python harness/check_claude_imports.py` if present;
   - `pytest --collect-only`;
   - the existing test suite if feasible.
8. Produce a Phase 0 report.

## Output required

Create or update:

- `docs/SPINE_PHASE0_INVENTORY.md`
- `docs/SPINE_PHASE0_MIGRATION_PLAN.md`

The report must include:

- changed files;
- tests run;
- failures or environment blockers;
- current direct-dependency map;
- behavior-change risk assessment;
- recommended Phase 1 scope;
- unresolved questions.

## Stop condition

Stop after Phase 0. Do not proceed into Phase 1 implementation.
