# WO-0028 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0028]

## done_when → met

1. **All 10 items landed (8 original + 2 amended-in), strengthen-only.**
   - TC-01: `or True` tautology deleted; the assertion now captures the working
     order's venue id pre-reprice and pins the replace target. Evidence: mutation
     M9 (replace aimed at `"totally-wrong-venue-order"` at the real call site,
     app/reconciliation.py) — previously survived 410 tests, now
     `FAILED ...reprice_leg_replaces...[memory]` + `[sqlite]`.
   - TC-02: new `test_ratchet_holds_when_atr_expands_and_candidates_collapse`
     (calm rise → ±0.25 whipsaw below the peak: ATR explodes, ref_high pinned,
     last candidate collapses below the calm-phase stop). M6 (`stop = candidate`)
     — previously survived the whole suite — now KILLED.
   - TC-03 (**app fix**): memory `_atomic()` now snapshots + restores
     `self._envelopes` (deep-copy, same pattern as orders). RED first:
     `test_memory_envelope_transition_is_all_or_nothing` and
     `test_memory_supersede_is_all_or_nothing` failed on unfixed code with the
     exact finding shape (envelope=APPROVED / SUPERSEDED while the log rolled
     back); GREEN after the fix; 4 memory crash-injection tests added
     (transition, staging, fill+dedupe-unpoisoned, supersede). New guard
     mutation M14 (restore line deleted) KILLED.
   - TC-04: `pytest.raises((OrderIntentBlockedError, EnvelopeTransitionError))`
     — M11 (staging raises KeyError) now KILLED (was: test passed with the
     crash in place).
   - TC-05: kill×approve race parametrized over BOTH serializations with exact
     per-ordering assertions (gather argument order + FIFO store lock force the
     schedule). M2 (kill-freeze hook disabled) is now killed by the race test
     itself (`[memory-approve-first]` FAILED), not only by the direct test.
   - TC-06: directed `@example([SUBMIT, REPRICE×5])` added to the venue-rail
     property. M5 (budget `>=`→`>`) now killed by the property ALONE
     (previously survived 3/3 property runs).
   - TC-07: exhausted-path union `(EXHAUSTED, FROZEN)` tightened to
     `is EXHAUSTED` — the signal, not just any freeze.
   - TC-08: `create_autospec(TradingClient, instance=True)` replaces the bare
     `Mock()`; M8 at the real call site KILLED (autospec raises on a renamed
     SDK method — upgrade-proof, closing the X-002 residual).
   - Item 9: `tests/test_rev0022_phase_a_pins.py` — 8 strict-xfail pins
     (F1, F3×3, F4, F5, F6×2) all xfailing for the right reason on both stores
     (16 xfailed), + 8 HELD interleaving probes promoted (16 passed).
   - Item 10: pre-existing ruff F841 at test_wo0021_envelope_chaos.py fixed
     (the `redriven` result is now asserted).
2. **Mutation matrix: 14/14 KILLED** (13 critic mutations incl. M1/M1b, + new
   M14). Runs scripted (scratchpad mutation_matrix{,2}.py), each mutation
   applied to committed code, targeted scope run, `git checkout` restore.
   Pass-1 note: M8 first "survived" because the locator mutated the DOCSTRING
   occurrence of the method name; at the call site it is killed — recorded to
   keep the evidence honest.
3. **Full gate green:** `ruff check` OK (including the previously-red F841),
   `ruff format --check` OK, `mypy app/` 64 files OK, `lint-imports` 6 kept /
   0 broken, `pytest -q` exit 0, zero FAILED/ERROR lines, 2591 collected
   (3 pre-existing xfails + 16 new pin-xfails among them).

## Incidents (visible)

- **Repeat of the WO-0017 git-checkout incident:** `git checkout -- app/store/memory.py`
  after the M11 probe wiped the then-uncommitted `_atomic` fix. Detected
  immediately (grep for `saved_envelopes` came back empty), re-applied from the
  identical scripted patch, re-verified 30/30, and the working practice was
  changed mid-WO: everything is committed BEFORE any mutation run (all
  subsequent matrix runs mutate committed code only). Root cause: same as last
  time — reflexive `git checkout` on a file carrying uncommitted work.
- **WO-0021 gate-claim correction:** baseline `ruff check` was RED at the
  merged tip f092ca7 (F841). The WO-0021 close-out's "full gate green" claim
  did not hold at the tip; fixed here, honestly recorded.

## Scope check

Allowed paths only: app/store/memory.py (one snapshot/restore pair) + tests/**.
No behavior change to any trading surface; diff is strengthen-only (no
assertion weakened, no test deleted).

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
