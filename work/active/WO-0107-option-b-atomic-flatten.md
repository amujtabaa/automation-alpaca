---
type: Work Order
title: Option B — atomic flatten redesign (store detects live BUYs under its own lock; no self-cross mint)
status: REVIEW
work_order_id: WO-0107
wave: R2 consolidation campaign (CAMPAIGN-0002), Part B — carved out of WO-0105's Part B umbrella
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-17
gated_surface: manual flatten (the store's flat/blocked/buys-open decision — a human-gated surface)
---

# Work Order: Option B — atomic flatten redesign

## Goal

Close the `create_exit` flatten lock-discipline finding (surfaced by the I.6 third-party review,
recorded in `FACADE-FLATTEN-LOCK-DISCIPLINE-DECISION.md`) at its **root**: stop the facade from
making a flat/blocked flatten decision on a **stale, out-of-lock** `get_position` read, and stop it
relying on callers to have cancelled open BUYs first. Instead, the store — under its own single lock
hold — is the sole authority on the flatten outcome, and it **refuses to mint a `MANUAL_FLATTEN`
SELL next to a still-open BUY** (the §5.3 self-cross), signalling the caller to cancel the BUYs
(a broker call, never under the store lock) and RETRY.

This is the operator-ratified **Option B** from the decision memo ("Option B. Then the downstream
pieces.", 2026-07-16 addendum to `RATIFICATION-part-a.md`). The memo's recommendation, verbatim:
"Queue it as its own small WO with independent review, since it changes the store's human-gated
flatten decision." This WO is that vehicle.

## Context packet

- `work/review/CAMPAIGN-0002-claude/FACADE-FLATTEN-LOCK-DISCIPLINE-DECISION.md` — the three options
  (0/A/B), the two contradicting independent reviews, and why the naive guarded patch is a
  **confirmed regression** (it opens a self-cross window on a genuinely-flat symbol).
- `work/review/CAMPAIGN-0002-claude/RATIFICATION-part-a.md` — the 2026-07-16 addendum recording the
  operator's Option B choice.
- `CLAUDE.md` safety core — manual flatten is a **human-gated surface**; "never weaken a test to make
  code pass"; the single-writer / lock-discipline invariants (`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`
  §5 INV-1..9, X-001 "the whole flatten decision under ONE lock hold").
- `app/monitoring.py::cancel_open_buys` (the caller-side broker cancel) + `OPEN_BUY_STATUSES`.

## Allowed paths

Single consecutive block (the `check_work_order_scope.py` parser reads only an unbroken run of `- `
list items). This WO **carves the flatten-redesign change out of WO-0105's Part B umbrella**: these
same app paths also appear in WO-0105's pre-declared Part B scope, but the flatten-decision change
is owned and reviewed here so it gets its own disposition + independent-review gate. `app/store/base.py`
(the store ABC / `FlattenResult` vocabulary) is added here — it was an oversight in WO-0105's list
(the three concrete stores were listed, the ABC they share was not).

```yaml
allowed_paths:
  - work/active/WO-0107-option-b-atomic-flatten.md
  - work/review/CAMPAIGN-0002-claude/**
  - work/review/REV-0024/**
  - work/ledger.jsonl
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/monitoring.py
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical.
  - work/review/CAMPAIGN-0002-codex/** (any other investigator's report path — independence rule).
```

## Required behavior

1. **Store is the single authority.** `flatten_position` (both `InMemoryStateStore` and
   `SqliteStateStore`) finds the symbol's still-open BUYs — those in
   `OPEN_BUY_STATUSES = {CREATED, SUBMITTED, PARTIALLY_FILLED}` — **under the same lock hold** that
   reads position/intent/order and applies the decision. The set matches exactly what
   `cancel_open_buys` clears, so the caller's cancel + retry provably converges.
2. **No self-cross mint.** On a **held** position (`quantity > 0`) with any open BUY,
   `plan_flatten_position` short-circuits to `FLATTEN_BUYS_OPEN` — it mints **no** intent and **no**
   order and touches **no** BUY. Ordered *after* the flat/halted gates and *before* the
   existing/supersede/deferral logic, so: a genuinely-flat symbol still returns `FLATTEN_FLAT` with
   an unrelated resting BUY **untouched** (long-standing behavior, preserved), and a Halted-denied
   flatten never cancels BUYs.
3. **Facade cancel-and-retry.** `create_exit` drops the stale out-of-lock `get_position` pre-check
   and routes through a bounded helper: call `flatten_position`; on `FLATTEN_BUYS_OPEN`,
   `cancel_open_buys` (broker call, **not** under the store lock) then retry; bounded at
   `_FLATTEN_MAX_BUY_CANCEL_ATTEMPTS = 3` → **fail closed** (raise `ConflictError`) if BUYs keep
   reappearing, never loop forever, never mint next to a live BUY. `emergency_reduce_override` keeps
   its unconditional `cancel_open_buys` then routes through the same helper.
4. **Both stores tested.** In-memory and SQLite parity for the new `FLATTEN_BUYS_OPEN` path
   (state/order/position surface — repo testing rule).
5. **No test weakened.** The two `_hold`/inline fixtures that left the establishing BUY in `CREATED`
   (a phantom open BUY) are corrected to terminalize it (`CREATED → CANCELED`, the only valid direct
   edge) — a **realism** fix reflecting that a truly-held position has no lingering open BUY, not a
   weakening: the envelope-precedence and atomic-flatten assertions those tests pin are unchanged.

## Done-when

- [x] `plan_flatten_position` gains `open_buy_order_ids` + `FLATTEN_BUYS_OPEN` short-circuit (core.py).
- [x] `FLATTEN_BUYS_OPEN` `FlattenResult` constant + updated `flatten_position` contract (base.py).
- [x] Both stores detect open BUYs under the lock and return `FLATTEN_BUYS_OPEN` (memory.py, sqlite.py).
- [x] Facade bounded cancel-and-retry helper; stale pre-check removed (store_backed.py).
- [x] `OPEN_BUY_STATUSES` shared from core into monitoring (single source of the open-BUY set).
- [x] New pin suite `tests/test_wo0036_r2_flatten_buys_open.py` (14 cases w/ `any_store`): held+live-buy
      → BUYS_OPEN no mint; held+CREATED-buy → BUYS_OPEN; flat+buy → FLAT buy untouched; held+no-buy →
      CREATED; facade cancels+retries → created; facade flat+buy → 409 buy untouched; facade
      fails-closed on buys-keep-reappearing.
- [x] Corrected fixtures: `test_phase7_flatten_atomic.py`, `test_wo0036_r2_lifecycle_link.py`,
      `test_wo0017_precedence.py`, `test_wo0021_envelope_chaos.py`.
- [x] Taught the `FLATTEN_BUYS_OPEN` outcome to `test_lifecycle_state_machine.py` (the Hypothesis
      state machine asserted `intent is not None` for any non-flat outcome → a flaky false X-001
      failure on a held-position-with-open-buy state), + a deterministic reachability proof of the
      new branch on both stores. (Test-integrity review DEFECT-1.)
- [x] Native gate green: `ruff check .` + `ruff format --check` + `mypy app/` (64 files) +
      `lint-imports` (6/0) + full `pytest` (0 failures, 0 errors).
- [x] AI-OS hygiene green: install / version / ledger / pkl / disposition all PASS.
- [x] In-process adversarial pass: concurrency **SHIP**, behavior/self-cross **SHIP**,
      test-integrity **TESTS-SOUND** (fixtures not weakened; two incompleteness defects found + one
      fixed, one routed to the human — see below). Summarized in `../REV-0024/request.md`.
- [x] **RESOLVED (operator ratification D1, 2026-07-17) — Codex spec-oracle conflict
      (test-integrity DEFECT-2).** The operator ratified the setup-only reseed of the 10 affected
      scenarios as a recorded spec change (`RATIFICATION-partb-completion.md` D1; dual-baseline
      proof in `PARTB-COMPLETION-PLAN.md` §6-P1). The Codex oracle is now fully green (61/0).
      Original analysis: `../CAMPAIGN-0002-claude/OPTIONB-CODEX-ORACLE-CONFLICT.md`.
- [ ] **Independent cross-model review dispositioned `ACCEPT` / `ACCEPT-WITH-CHANGES` — now via
      REV-0029** (REV-0024 subsumed per ratification D4; see `../REV-0024/SUPERSEDED.md`).
      This is a **human-gated flatten surface** — per CLAUDE.md the review gate clears only on that
      verdict, and no beta-relevant milestone may rely on Option B until it does. **status stays
      `REVIEW` until then.**

## Disposition (on close)

RESULT_SUMMARY_KEPT (this WO + the decision memo are the durable record). Ledger row + status flip to
CLOSED ship in the same commit that records the independent-review ACCEPT — not before.
