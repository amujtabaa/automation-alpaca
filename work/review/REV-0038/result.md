---
type: Review Result
rev_id: REV-0038
reviewer: "Claude (independent; builder Codex)"
commit_range: cf50f115c55b04d2111a17ec9207b004dd4b8b7e..b99d8c03ca56fbba66f21ce958da2b0364c72df6
branch: codex/ultra-beta-batch (reviewed at d589da4)
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-21
---

# REV-0038 — independent review of WO-0131 (envelope replay FSM legality)

All work re-derived in a throwaway worktree of `d589da4` (and of the pre-fix parent
`b99d8c0~1` = `d0665b3`, whose app code is identical to base `cf50f11`) in an isolated
scratch directory; pytest basetemp in scratch; every mutation restored before writing this.
Builder claims were treated as claims and reproduced, not trusted.

## Core red→green evidence (original defect reproduced first)

**Pre-fix (`b99d8c0~1`), my own probe (not the builder's tests):** a correctly shaped
synthetic `PENDING → COMPLETED` was **ACCEPTED, final=completed** by BOTH
`project_envelopes` and `project_read_models`. Likewise accepted pre-fix: the deliberate
`FROZEN → COMPLETED` non-edge, `ACTIVE → CANCELLED`, an outgoing edge from **every one of
the six terminal states** (two each), and an `ACTIVE → ACTIVE` self-transition — 26/26
illegal probe checks accepted. The builder's new pin
`test_replay_rejects_every_fsm_illegal_envelope_transition[pending-to-completed]` fails
pre-fix with `DID NOT RAISE ProjectionError`; the full test file at the pre-fix parent is
**75 failed / 30 passed** — the 75 failures are exactly the illegal-edge matrix.

**Post-fix (`d589da4`):** the identical probe set is 38/38 OK — every illegal case raises
`ProjectionError: illegal envelope transition ...` from both paths; every legal case
(`ACTIVE→FROZEN→ACTIVE`, `ACTIVE→FROZEN→BREACHED`, `FROZEN→CANCELLED`) projects to the
exact expected final status. `tests/test_wo0125_envelope_replay_parity.py` = **106 passed**.

The check is `app/events/projectors.py:705-709`: after the identity/`from`/`to`
validation and **before** any status/supersession mutation, `expected` (event-type
derived, never payload-derived) must be in `ENVELOPE_TRANSITIONS[current.status]`
(projected current, not payload). `app/transitions.py:59-93` is consumed read-only —
untouched in the range. Sole aggregate consumer `app/events/replay.py:192` calls
`project_envelopes` with no try/except — the exception propagates; no alternate replay
path exists (`grep` over `app/` finds no other caller).

## Exhaustiveness (independently derived, not read off the tests)

I recomputed the matrix from `EnvelopeStatus` × `ENVELOPE_TRANSITIONS` myself: 10 source
states × 9 representable targets (PENDING has no producing event —
`_ENVELOPE_STATUS_EVENTS`, projectors.py:465-476, maps no event to PENDING) = **90 pairs;
15 legal / 75 illegal**. The collected pytest IDs equal my derived sets **exactly** (set
equality both directions, disjoint, union = 90): `frozen-to-completed` and
`active-to-cancelled` are in the reject matrix, `frozen-to-cancelled` in the accept set,
and all **54** terminal-source pairs are enumerated — full enumeration, not sampling.

## No legitimate stream newly rejected

- Full corpus on the target ref — `test_wo0125_envelope_replay_parity.py`,
  `test_phase6b_readmodel_parity.py`, `test_wo0007a_stage4_dual_store_parity.py`,
  `test_wo0036_r2_parity_adversarial.py`, `test_wo0036_r2_projection_scope_parity.py`,
  `test_wo0113_store_parity.py`, plus both oracles `tests/r2_conformance_oracle.py` and
  `tests/test_r2_conformance_oracle_claude.py`: **282 nodes, 276 passed / 6 pre-existing
  documented NEEDS-INPUT skips, exit 0** (matches builder).
- My own real-producer probe: drove memory AND SQLite stores through
  PENDING→APPROVED→ACTIVE→FROZEN→ACTIVE→FROZEN→CANCELLED via `transition_envelope`,
  replayed the persisted logs: replay == aggregate == store read model on both stores.
  Producers cannot emit off-graph edges: `app/store/core.py:4552` refuses non-graph
  transitions pre-write from the same `ENVELOPE_TRANSITIONS`.

## No test weakened

Range test diff removes lines only inside `test_terminal_lifecycle_event_folds_status`'s
parametrization. All six terminal folds are retained; only the CANCELLED fold's source
moved from ACTIVE to FROZEN — justified: `ACTIVE → CANCELLED` was never a canonical edge
(transitions.py has no such edge), and it is now explicitly negative-pinned
(`[active-to-cancelled]` red-verified below). Everything else is additive.

## Mutation pass (all restored; decisive node IDs verified)

| Mutation (projectors.py:705) | Result |
|---|---|
| M1 — disable graph check (`if False and ...`) | **76 red**: all 75 illegal matrix nodes + `test_read_model_projection_rejects_fsm_illegal_envelope_transition`. Both paths kill. |
| M3 — exempt terminal sources (`if ENVELOPE_TRANSITIONS[current.status] and ...`) | **exactly 54 red** — every terminal-source node. |
| M3b — exempt `ENVELOPE_COMPLETED` | **10 red** — all 9 illegal `*-to-completed` nodes (incl. `frozen-to-completed`) + the aggregate pin. |
| M4 — additionally reject legal `FROZEN→ACTIVE` | **4 red**: `[frozen-to-active]`, `test_replay_folds_actions_fills_attribution_freeze_and_resume`, and real-store `test_projection_matches_each_store_read_model[memory]` + `[sqlite]`. |
| M2 — key graph on payload `from` AND remove the `from` guard | **SURVIVES: 106 passed + corpus green** → Finding F1. |

## Findings

### F1 (P2 — drives ACCEPT-WITH-CHANGES): payload-`from`/`to` consistency guards are unpinned; request mutation (b) survives green
- **Where:** `app/events/projectors.py:694-704` (pre-existing WO-0125 guards; adjacent to the WO-0131 check they feed).
- **What:** No test anywhere in the suite constructs a status event whose payload `from`/`to`
  contradicts the projected state or event type (`grep "does not match"` over `tests/` = 0 pins).
  Applying the request's mandated mutation (b) — remove the `from` guard and key the graph
  check on the payload's `from` claim — leaves `test_wo0125_envelope_replay_parity.py`
  **106 passed** and the parity corpus green. Under that mutant I demonstrated the concrete
  corruption: an `ENVELOPE_COMPLETED` on a PENDING envelope whose payload lies
  `{"from": "active", "to": "completed"}` is **ACCEPTED, final=completed** — a de-facto
  `PENDING → COMPLETED`, the exact class WO-0131 exists to forbid, with a fully green suite.
- **Why it matters:** the `from` guard is load-bearing for the fail-closed contract (the graph
  check alone is only as honest as the state it is keyed on); an unpinned load-bearing rail is
  the REV-0029 inert-pin class, and the request explicitly instructs reporting it.
- **Not a defect of the delivered change:** the guards predate WO-0131, the WO's own check is
  real and killable (M1/M3/M3b/M4), and the projector as shipped uses `current.status`, not payload.
- **Resolves:** additive pins — a from-mismatch event (payload `from` ≠ projected status) and a
  to-mismatch event (payload `to` ≠ event-type target) each raising `ProjectionError`, direct +
  aggregate. Tests only; no source change needed.

### F2 (P3): event-vocabulary/edge pairing not enforced (graph-level only)
Synthetic `ENVELOPE_ACTIVATED` folding FROZEN→ACTIVE and `ENVELOPE_RESUMED` folding
APPROVED→ACTIVE are both ACCEPTED (probe-verified): both land on the graph-legal
status edge, but neither is an event the producers would emit for that source
(`app/store/core.py:4388` — FROZEN→ACTIVE is RESUMED). Within the WO's stated contract
(graph membership) this is compliant; optional future hardening could pin event-type ↔
source-state pairing. No action required for this packet.

### F3 (P3 — environment): verified under Python 3.11.15; repo pins 3.12 (same limitation REV-0035 recorded as P2-2). `mypy` ran as `python -m mypy` (env module), not the repo's pinned toolchain binary.

### F4 (observation): the aggregate pin `test_read_model_projection_rejects_fsm_illegal_envelope_transition` was introduced in the same commit as the fix (`b99d8c0`), so it has no committed red state; its failure-capability is instead proven by M1/M3b (it goes red). Noted for red-first bookkeeping only.

## Properties table

| # | Property (request §Authority/behavior) | Verdict |
|---|---|---|
| 1 | `ENVELOPE_TRANSITIONS` sole canonical graph, consumed unmodified; no import cycle (lint-imports 6 kept / 0 broken) | VERIFIED |
| 2 | from==projected, to==event-target, then graph membership on projected enum; payload never picks the node (in unmutated code) | VERIFIED (but see F1: the from/to guards themselves are unpinned) |
| 3 | Illegal edge raises ProjectionError before any mutation (PENDING→COMPLETED, ACTIVE→CANCELLED, FROZEN→COMPLETED, all terminals, self-transitions) | VERIFIED (probe + 75-red pre-fix) |
| 4 | Every legal edge projects incl. escape edges, ACTIVE↔FROZEN, FROZEN→CANCELLED/BREACHED; FROZEN→COMPLETED non-edge observable | VERIFIED |
| 5 | Matrix = full 10×9 cross-product, no dups/omissions; PENDING has no target event | VERIFIED (independent set-equality) |
| 6 | Terminal fixture strengthened, not weakened | VERIFIED |
| 7 | `project_read_models` propagates; no bypass/swallow path | VERIFIED |
| 8 | Real memory+SQLite producer streams replay clean; producer/graph agreement | VERIFIED |
| — | Mutation battery (request list) | 3 of 4 kill correctly; mutation (b) SURVIVES → F1 |
| — | Scope: commits touch only allowed paths; forbidden paths untouched; `git diff --check` clean | VERIFIED |

## Ran vs read

**Ran** (worktrees of `d589da4`, `b99d8c0~1`, `cf50f11` in isolated scratch; basetemp in scratch):
pre-fix probe (26 illegal accepted / legal OK); post-fix probe (38/38); pre-fix pin red +
75F/30P full file; post-fix 106 passed; baseline at `cf50f11` = **14 passed** (matches claim);
corpus 282 nodes exit 0; real-store dual-producer probe; vocabulary-nuance probe; mutation
battery M1/M2/M3/M3b/M4 with per-node red verification and restore-to-pristine checks
(`git status --porcelain` = 0 before every teardown); `ruff check .` → All checks passed;
`python -m mypy app/` → Success, 70 files; `lint-imports` → 6 kept / 0 broken;
full suite on `d589da4`: **4205 collected; 4193 passed / 11 skipped / 1 xfailed; exit 0**
(counts re-derived from the progress glyphs; matches builder's 4205/11/1).

**Read:** WO-0131 contract + Fable record, REV-0038 request, AGENTS.md rubric, CLAUDE.md
safety core, `app/events/projectors.py`, `app/transitions.py`, `app/events/replay.py`,
full commit diffs `cf50f11`, `d0665b3`, `b99d8c0`, `d759913`, and the producer-side
`ENVELOPE_TRANSITIONS` consumers in `app/store/{core,memory,sqlite}.py`.

## Could not verify

1. Pinned-toolchain run: environment is Python 3.11.15, repo pins 3.12 (F3); CI-form
   coverage invocation not reproduced.
2. Builder's exact runtime/format-authority environment (his 395.6s wall time, uv-mypy binary).
3. Skip/xfail identities in the full suite beyond counts (verified 11 s + 1 x glyphs, and the
   6 corpus skips are the documented NEEDS-INPUT trio × 2 params).

## Verdict

**ACCEPT-WITH-CHANGES.** The delivered fix is correct, minimal, in scope, and genuinely
fail-closed against the canonical graph; the original defect is independently reproduced
and the fix independently kills it across both replay paths, with a truly exhaustive
90-pair matrix and no producer stream newly rejected. Required change (tests only, no
source edit): add the payload `from`/`to` mismatch pins of F1 so the request's mutation (b)
becomes killable; until then the fail-closed contract rests on an unpinned guard.
