# CLAUDE.md — Alpaca Spine v2 Agent Operating Contract

For Claude Code, Codex, or any AI coding agent working in this repository.

This file is the **repo-level operating contract**. It governs *how* agents work. The v2 execution-spine design, accepted decisions, and phase roadmap govern *what* to build.

> Project: **Alpaca Clean-Sheet CAPI Option 2.5** — a browser-operated, paper-first Alpaca Paper Trading platform being upgraded into a safer execution spine for capital protection and exit management.

Safety and correctness outrank feature velocity.

---

## 0. Current migration posture

This repo is **not** a clean-sheet rewrite.

The correct strategy is:

1. **salvage** mature prior-repo components that are already tested and sound;
2. **re-architect** the safety-critical execution path around Spine v2;
3. **migrate in phases** with characterization tests, event-log replay, dual-store parity, and independent review.

Do not implement the full execution engine in one pass. Do not begin Phase N+1 on an unreviewed Phase N branch.

---

## 1. Canonical read order for Spine v2 work

Before writing code for the Spine v2 upgrade, read in this order:

@docs/00_START_HERE_SPINE_UPGRADE.md
@docs/SPINE_EXECUTION_ARCHITECTURE_v2.md
@docs/SPINE_V2_ACCEPTED_DECISIONS_ADDENDUM.md
@docs/MIGRATION_MATRIX.md
@docs/REARCHITECTURE_ROADMAP.md

Then read the accepted ADRs relevant to the change:

@docs/adr/ADR-001-overfill-quarantine.md
@docs/adr/ADR-002-timeout-quarantine.md
@docs/adr/ADR-003-manual-flatten-halted-reducing.md
@docs/adr/ADR-004-event-log-truth-migration.md
@docs/adr/ADR-005-api-facade-boundaries.md

For current implementation facts, also consult the legacy/current architecture docs:

@docs/01_ARCHITECTURE.md
@docs/02_DATA_AND_PERSISTENCE.md

### Conflict rule

If legacy docs or older implementation prompts conflict with the Spine v2 spec or accepted ADRs:

1. **Do not silently pick one.**
2. Treat current code and legacy docs as evidence of existing behavior.
3. Treat Spine v2 spec + accepted ADRs as the target architecture for migrated flows.
4. If the conflict affects safety, state mutation, order submission, reconciliation, kill switch, or broker facts, stop and record the decision gap before coding.

Older `IMPLEMENTATION_PROMPT_*` files are historical artifacts unless explicitly reactivated by a human.

---

## 2. Stack and substitution rules

Pinned stack for this project:

- **Python 3.12** target runtime.
- **FastAPI** backend / engine.
- **Streamlit** thin cockpit.
- **alpaca-py** only inside the concrete Alpaca adapter.
- **SQLite** + in-memory store.

Do not introduce React, Dash, TradingView Advanced Charts, Webull, IBKR, TradersPost, or another broker platform for this Alpaca beta.

Do not add a dependency without:

1. a decision-log / ADR entry justifying it;
2. verifying current package/API status against official docs or PyPI;
3. preferring stdlib or existing project infrastructure when feasible.

---

## 3. Non-negotiable invariants

Never violate these. They are acceptance criteria.

1. No live trading in beta — `PAPER` or `LIVE_SHADOW` only; live modes disabled by config.
2. Alpaca Paper only for beta.
3. FastAPI backend is the durable engine and source of truth.
4. Streamlit is a thin client — observes state and issues intents; never mutates state directly.
5. The UI never calls Alpaca — only the Broker Adapter does.
6. The UI owns no strategy/risk/order/fill/position state.
7. All important logic lives in the backend.
8. Submitted does **not** equal filled.
9. Only fill events change position quantity.
10. Kill switch blocks new order intent.
11. Browser-first workflow.

Spine invariants **INV-1 … INV-9** in `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5` are also acceptance criteria.

Do not weaken a test to make code pass. Fix the code or flag the spec/code conflict.

---

## 4. Accepted architecture decisions

These decisions are binding for migrated Spine v2 flows:

1. **Broker-authoritative overfill facts are recorded and quarantined.** Malformed local/internal input may be rejected, but broker-reported reality must not be hidden.
2. **Timeout/504/ambiguous submit outcomes become `TIMEOUT_QUARANTINE`.** Use deterministic `client_order_id` for reconciliation, not blind redrive.
3. **Manual flatten is allowed in `Reducing`, blocked in `Halted` by default, and allowed from `Halted` only through explicit audited emergency reduce override.**
4. **The v2 execution spine migrates to event-log-as-truth in phases.** Legacy state tables may temporarily remain as read models/compatibility projections.
5. **FastAPI routes must migrate behind typed command/query facades.** Streamlit imports only the typed API client. The Alpaca SDK is imported only by the concrete adapter.

---

## 5. Architecture boundaries

The system is layered. Imports may only flow through approved seams.

Target boundaries:

- `ui` / Streamlit → may import only the typed API client and UI-local display helpers.
- `api` / FastAPI → schemas, auth, and command/query facades only.
- `facade` → command/query protocols, readiness checks, DTO mapping, and domain error mapping.
- `engine` → venue-agnostic execution, risk, session control, reconciliation, position projection, and event ingestion.
- `adapter` → concrete broker implementation; the only place allowed to import `alpaca-py`.
- `store` → event log, snapshots, projections, parity verifier, and legacy read models.

Single-writer rule:

- Only the Execution Engine mutates order/fill/position state for migrated flows.
- Position Service derives position only from deduped fill events.
- `SUBMITTED` / `ACCEPTED` events must be structurally unable to change position quantity.

Enforce boundaries with import-linter once the migration seams exist. A PR that crosses a protected boundary fails CI.

---

## 6. Phase discipline

Use one branch, one phase, one working context.

Each new coding session must:

1. verify repo state;
2. read this `CLAUDE.md` and the current phase start document;
3. run the existing test suite or the phase harness;
4. identify whether the target flow is `legacy_truth`, `shadow_evented`, or `event_truth` in `docs/MIGRATION_MATRIX.md`;
5. preserve existing behavior unless the phase explicitly migrates that behavior.

Do not claim completion from code reading alone. Reproduce behavior through tests on both in-memory and SQLite paths when the change touches state, order, fill, position, reconciliation, kill switch, or API boundary.

---

## 7. Testing and determinism

Required testing posture:

- Preserve and extend the existing test corpus.
- Add characterization tests before changing behavior.
- Add property tests for Spine invariants where a behavior spans many interleavings.
- Use deterministic clocks/IDs/queues in engine logic.
- No bare `datetime.now()` / `time.time()` in engine logic; inject a clock.
- No unseeded randomness in engine/reconciliation tests.
- Persist or print failing property-test seeds/traces when possible.
- Test memory + SQLite parity for any store-impacting behavior.
- Add replay/parity verifier coverage as event-log migration lands.

Changes touching overfill, timeout ambiguity, reconciliation, kill switch, manual flatten, or position projection must expand tests in the same phase.

---

## 8. CI and harness gate

Target PR gate:

- `ruff` lint / complexity where configured.
- `mypy` where configured.
- `pytest` + coverage.
- import-linter boundary checks once contracts are enabled.
- dependency vulnerability check such as `pip-audit` once configured.
- event-log replay / parity verifier once implemented.

During Phase 0, use the provided harness scripts as smoke/inventory tools, not as a substitute for the full test suite.

---

## 9. Stale artifact handling

Older implementation prompts may contain useful historical reasoning, but they are not current instructions.

Default handling:

- Move stale `docs/IMPLEMENTATION_PROMPT_*` files to `docs/archive/legacy_implementation_prompts/` with a README explaining historical status.
- Do **not** delete decision logs, architecture docs, tests, or source files unless a human explicitly confirms deletion.
- Delete generated cache artifacts such as `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, and coverage outputs if present.
- Do not archive tests merely because their names contain old phase numbers. Phase-named tests are still active regression evidence unless replaced and reviewed.

Use `docs/STALE_ARTIFACT_CLEANUP_GUIDE.md` for details.

---

## 10. Safety rails

Never generate, enable, or accidentally expose live-trading paths during beta.

Treat ambiguous broker responses as `TIMEOUT_QUARANTINE` and reconcile. Never blind-resubmit a request that may have reached Alpaca.

Fail fast on invalid market data. A stale, NaN, negative, or out-of-range quote must halt, degrade, or quarantine the relevant flow; it must not drive sizing/submission decisions.

Broker-authoritative overfill/negative-position facts must be recorded and quarantined; do not hide broker reality by rejecting the event out of the local projection path.

Manual flatten must route through session control, risk/quantity checks, event logging, and the single-writer engine. It is not a global bypass.

---

## 11. Review and merge discipline

Use the three-seat model:

1. Planning seat architects and accepts decisions.
2. Claude Code implements a bounded phase.
3. Codex / ChatGPT / separate seat performs independent adversarial review.
4. Planning seat calibrates, reproduces, and accepts or sends back for remediation.

No seat reviews its own work as the only review.

The implementer writes or updates the ADR/decision record as part of the fix, not afterward.

At phase close, perform a consolidation sweep:

- remove duplicate abstractions;
- update migration matrix;
- update invariants/ADRs if behavior changed;
- update this file if agent operating rules changed;
- run tests/harness;
- stop for independent review.
