---
type: Testing Rule
title: Testing Model and Determinism Rules
status: active
authority: high
owner: Ameen
last_verified: 2026-07-08
tags: [testing, determinism, ci]
source_refs: [docs/SPINE_EXECUTION_ARCHITECTURE_v2.md]
supersedes: []
superseded_by: null
---

# Testing Model and Determinism Rules

## Summary

Deterministic, dual-path testing posture inherited from the migration and kept permanently: engine logic must be replayable, and any state-touching change proves itself on both stores.

## Rules / facts

- Engine logic: injected clock only — no bare `datetime.now()` / `time.time()`. No unseeded randomness in engine/reconciliation tests. Deterministic IDs and queues.
- Dual-store parity: any change touching state, order, fill, position, reconciliation, kill switch, or the API boundary is tested on both in-memory and SQLite paths.
- Safety-surface changes (overfill, timeout ambiguity, reconciliation, kill switch, manual flatten, position projection) expand tests in the same change — never deferred.
- Property tests cover spine invariants where behavior spans many interleavings; persist or print failing seeds/traces.
- Replay / parity verifier runs where implemented; event-log replay is regression evidence.
- Never weaken a test to make code pass; never merge failing or newly-skipped tests. Phase-named tests remain active regression evidence unless replaced and reviewed.
- CI gate (as wired today): `ruff check`, `mypy app/`, `pytest` + coverage, import-linter (`lint-imports`) contracts, `pip-audit` where configured. Formatting authority: `ruff format`.
- `mypy` static typecheck (ADR-007, wired 2026-07-08): baseline-and-ratchet over `app/` via `pyproject.toml [tool.mypy]` — 16 grandfathered modules (`ignore_errors`); new/clean modules are checked; the punch-list only shrinks (burn down `store/*`, `monitoring`, `policy` first). Baseline was 187 errors/16 files (pydantic plugin + ignore-missing-imports). Known limitation: a new error inside a grandfathered module isn't caught until that module is cleaned.

## Rationale

Determinism is what makes broker-edge-case behavior (timeouts, overfills, interleavings) reproducible enough to trust. Dual-path testing was the migration's parity guarantee and remains cheap insurance.

## Applies to

- All tests; CI configuration; every state-touching work order.

## Related pages

- `pkl/architecture/architecture-map.md`
- `pkl/safety/invariants-rationale.md`

## Change log

- 2026-07-07: Created from CLAUDE.md §7/§8 decomposition.
- 2026-07-08: Corrected the CI-gate list to what is actually wired (removed the unwired `mypy`); recorded `mypy` as a deferred gate with a measured baseline (193 errors) and a WO-0008 pointer. last_verified refreshed for the gate facts.
