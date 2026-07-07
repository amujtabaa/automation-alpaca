# 00 Start Here — Spine v2 Upgrade

## Purpose

This document is the entry point for the Alpaca Spine v2 upgrade. It explains the current posture, canonical read order, and phase discipline for Claude Code or any coding agent working in this repository.

## Current posture

This is **not** a clean-sheet rewrite. The prior Alpaca Paper Trading repository contains mature behavior worth salvaging, including dual in-memory/SQLite stores, shared planner logic, append-only fills, idempotent client-order infrastructure, manual-flatten hardening, protection-floor behavior, and a substantial regression suite.

The Spine v2 upgrade re-architects the safety-critical execution path around:

- single-writer execution;
- primary/spawn lifecycle;
- event-log-as-truth for migrated flows;
- broker-authoritative fact recording;
- timeout/504 quarantine;
- explicit TradingState policy;
- typed API facades;
- import-boundary enforcement;
- replay and dual-store parity.

## Read order

1. Root `CLAUDE.md`.
2. This file.
3. `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`.
4. `docs/SPINE_V2_ACCEPTED_DECISIONS_ADDENDUM.md`.
5. `docs/MIGRATION_MATRIX.md`.
6. `docs/REARCHITECTURE_ROADMAP.md`.
7. ADRs in `docs/adr/`.
8. Current repo docs, especially `docs/00_START_HERE.md`, `docs/01_ARCHITECTURE.md`, `docs/02_DATA_AND_PERSISTENCE.md`, and `docs/INVARIANTS.md`.

## Source-of-truth rule

For migrated Spine v2 flows, the Spine v2 spec and accepted ADRs define the target behavior. Legacy docs and current code remain evidence of current behavior and regression expectations.

Do not silently resolve conflicts. If a conflict affects order submission, fills, positions, reconciliation, kill switch, manual flatten, broker facts, or API boundaries, stop and record the gap before coding.

## Phase 0 objective

Phase 0 is not an engine rewrite. It should:

- install/update operating docs;
- archive stale implementation prompts;
- add facade/event/harness seams only if explicitly tasked;
- add characterization tests before behavior changes;
- run test collection and report the current baseline;
- stop for review.

## What not to do in Phase 0

- Do not change production trading behavior.
- Do not enable live trading.
- Do not rewrite the execution engine.
- Do not remove tests because they reference older phase names.
- Do not treat old implementation prompts as current instructions.
