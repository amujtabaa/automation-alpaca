---
type: Module Knowledge
title: Architecture Map (Spine v2, as-built)
status: active
authority: high
owner: Ameen
last_verified: 2026-07-08
tags: [architecture, boundaries, layers]
source_refs: [docs/SPINE_EXECUTION_ARCHITECTURE_v2.md, docs/adr/ADR-005-api-facade-boundaries.md, docs/01_ARCHITECTURE.md]
supersedes: []
superseded_by: null
---

# Architecture Map (Spine v2, as-built)

## Summary

Layered system with strict import seams and a single-writer execution engine. Event log is truth for migrated flows (per ADR-004); legacy tables persist only as read models where noted in the migration matrix. The matrix is substantially complete but **not strictly terminal** (WO-0001, verdict NOT-TERMINAL narrow): one flow — the order-status / primary-spawn state machine ("Atomic submit claim") — is still `legacy_truth` (`orders.status` authoritative). Its ExecutionEvents are now emitted with faithful provenance (WO-0007a + WO-0009); the projector + read-flip that makes the matrix fully terminal is WO-0007b (queued, human-gated). See `pkl/process/migration-history.md`.

## Rules / facts

- Layers and seams:
  - `ui` (Streamlit) → imports only the typed API client + UI-local display helpers.
  - `api` (FastAPI) → schemas, auth, command/query facades only.
  - `facade` → command/query protocols, readiness checks, DTO mapping, domain-error mapping.
  - `engine` → venue-agnostic execution, risk, session control, reconciliation, position projection, event ingestion.
  - `adapter` → the only module allowed to import `alpaca-py`.
  - `store` → event log, snapshots, projections, parity verifier, legacy read models.
- Single writer: only the Execution Engine mutates order/fill/position state. Position Service derives positions only from deduped fill events. `SUBMITTED`/`ACCEPTED` events are structurally unable to change position quantity.
- Boundary enforcement: import-linter contracts in CI; a PR crossing a protected seam fails.
- Stack pins: Python 3.12, FastAPI, Streamlit, alpaca-py (adapter only), SQLite + in-memory store. New dependencies require an ADR and a current-status check against official docs/PyPI.

## Rationale

Seam discipline is what makes the safety invariants structurally enforceable rather than aspirational. See `pkl/safety/invariants-rationale.md`.

## Applies to

- All source and test code; CI boundary contracts.

## Related pages

- `pkl/architecture/testing-model.md`
- `pkl/safety/invariants-rationale.md`
- `docs/adr/` (ADR-001…ADR-005)

## Change log

- 2026-07-07: Created from CLAUDE.md §5/§2 decomposition. `last_verified` date reflects decomposition, not code audit; WO-0002…WO-0005 will verify against code.
