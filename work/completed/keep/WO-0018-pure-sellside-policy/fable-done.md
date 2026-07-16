# WO-0018 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0018]` — closed 2026-07-11, commit `def2501` on `feat/execution-envelope-wo-0018`. Reoriented mid-flight onto the FINAL planning drop (regime-adaptive spec + research notes) before any production code was committed.

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| decide() pure, injected clock, deterministic | ✅ | `test_wo0018_sellside_policy.py` (determinism, no input mutation) + hypothesis determinism property + bare-clock ban regression (`test_wo0018_sellside_hygiene.py`, grep over the package) |
| Hard rails breach, never clamp; soft bounds clamp+report | ✅ | floor-breach on stop-exit; validator matrix (floor/qty/cooldown/budget); ClampNote plumbing; hypothesis: no plan ever violates a rail (validate_action is the same function WO-0019 reuses at write time — D-3) |
| Stale/NaN/non-finite/out-of-range ⇒ fail closed + disposition | ✅ | 14 invalid-snapshot classes parametrized + empty tape + LEAVE_RESTING reporting |
| Bar aggregator / ATR / anchored VWAP / RVOL / quantile fade | ✅ | `test_wo0018_sellside_bars.py` (17 tests: OHLCV bucketing, reset-safe volume, gap-aware TR, VWAP deltas, RVOL warmup, fade strictness incl. chop + sub-noise immunity via the median-scale gate) |
| Regime classifier, five regimes, UNCERTAIN conservative | ✅ | synthetic tapes per regime; chop + warmup → UNCERTAIN; UNCERTAIN → widest trail |
| Regime→trail mapping; ratchet monotone; trail-floor invariant | ✅ | `test_wo0018_sellside_regime.py` + hypothesis (monotone over growing tapes; per-step candidate ≥ min_mult×ATR at max urgency). **Mutation-checked:** removing the ratchet's running max fails `test_working_stop_is_monotone_across_a_spike_then_crash` |
| Pullback discrimination | ✅ | contracting-volume pullback tolerated (no tighten); expanding-volume pullback snaps candidate to exactly min_mult×ATR |
| Tranche exits, participation-capped | ✅ | extension tape takes one half-remaining tranche ≤ participation; second tranche refused; stop-exit allows the 1-share probe, tranche path does not |
| Cooldown/budget from history only | ✅ | cooldown wait_until; ExhaustedSignal at budget; other envelopes' history ignored |
| Import contract CI-enforced | ✅ | `.importlinter` contract 6 (`sellside-is-a-pure-policy`); `lint-imports`: 6 kept, 0 broken; registration regression test |
| Full gate | ✅ | ruff check ✓ · format --check (204 files) ✓ · mypy 63 files ✓ · lint-imports 6/0 ✓ · pytest full suite exit 0, 0 failures |

## Scope check

Touched: `app/sellside/**` (new, 9 modules), `tests/test_wo0018_*` (7 files, 105 tests), `.importlinter` (contract addition only — the WO's `pyproject.toml` pointer was a drafting error, amended in the WO file), the WO file itself (divergence notes). `app/models.py` untouched (worktree overlap rule). Forbidden paths untouched.

## Divergences recorded (amended into the WO context packet)

1. LASE design docs 00/01/02/05 absent from the environment — design derived from ADR-010 §1/§2/D-4 + `pkl/architecture/sellside-research-notes.md` (authoritative per the final drop).
2. Import-linter contracts live in `.importlinter`, not `pyproject.toml`.

## Deferred log additions

- `ExecutionEnvelope.trail_distance_min/max` docstrings in `app/models.py` still say "trail distance"; under WO-0018(final) they are ATR MULTIPLES. models.py is forbidden here — a one-line docstring cleanup for WO-0020/cleanup.
- `compute_working_stop` recomputes indicators per bar prefix (O(n²)); fine at tick scale, revisit in the W4 harness if tapes grow.

## Status: VERIFIED
