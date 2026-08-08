# WO-0148 pre-fill lifecycle successor exact-delta review

### [P1] Pre-exposure provenance survives an authenticated fact-count advance at zero quantity

- Location: `app/execution_core/protection.py:1397` (the intended two-part predicate is at `app/execution_core/protection.py:1277-1287`).
- Requirement: The successor request and evidence require pre-exposure provenance to persist only while both raw quantity and canonical execution-fact count are zero. Zero after canonical execution history must not remain pre-exposure.
- Evidence: `reproduced-live`. I initialized the MSFT protection state from its genuine mandate-bound requested BUY at raw quantity 0 / execution-fact count 0. I then applied a real AAPL venue chain and canonical fill, followed by the existing authenticated `CatchUpExecutionRegistry` path that projects the current account registry into MSFT without changing MSFT quantity. The MSFT catch-up was `APPLIED`, execution binding matched, account reconciliation was clear, and its projection reported raw quantity 0 / fact count 1. The public protection reducer nevertheless retained `_pre_exposure_origin()`:

  ```text
  target_catchup disposition APPLIED raw 0 facts 1 binding True recon_clear True blocking 1 pre_exposure True
  target_first_fill raw 1 facts 2 formula True policy FLOOR_ONLY alert None
  ```

  `pre_exposure_zero` correctly evaluates false once the count is 1, but the later generic `raw_quantity == 0 and prior is not None` branch copies the prior pre-exposure provenance without rechecking the count. The following positive exact-basis fill therefore takes the special pre-exposure-to-genesis path and arms `FLOOR_ONLY`. The added post-history-zero control does not catch this because it initializes directly from a count-2 projection; it does not advance an already initialized pre-exposure state from count 0 to a positive count while quantity remains zero.
- Impact: Authenticated execution history can arrive through the explicitly supported multi-scope catch-up lane while protection is already initialized at zero. The state then remains indistinguishable from never-exposed pre-fill state and bypasses the intended post-history sticky `HARD_BAIL` distinction on the next positive economics. This falsifies the successor's central persistence claim even though projection authentication and the v2 count seal work as designed.
- Smallest root correction: In the zero-quantity provenance branch, do not preserve `_pre_exposure_origin()` when `projection._execution_fact_count > 0`; transition to the same non-prefill provenance used when initializing from post-history zero (subject to the existing `flat_ready` precedence). Add a real transition control for pre-exposure count 0 -> authenticated catch-up count > 0 at raw zero -> positive exact-basis fill, and retain the existing direct-initialization post-history control.

## Evidence reproduced

- Exact immutable boundary: `HEAD=2848b8540645dbd6c58e62dffa867e666b0c32f9`; merge base with `d3e11f31f16b55f1209f7e2b3f00a1b4056ca157` is the declared parent; the four changed paths exactly match the request; tracked state was clean. Historical untracked artifacts were ignored and preserved.
- Original genuine pre-fill chain: passed; the first 4 @ 100 canonical fill produced positive formula authority, `FLOOR_ONLY`, no alert, and no goal.
- Author's eight-case critical focus: 8/8 passed, including the two new controls, true-flat late positive, three multi-scope kill/catch-up cases, projection single-field forgery, and predecessor continuity.
- Both new controls killed an in-memory provenance-collapse mutant; neither is tautological, but neither covers the transition defect above.
- Focused restriction probes for reconciliation, negative overfill, positive overfill, pending basis, and formula loss: 5/5 passed.
- `python -m pytest -q -p no:cacheprovider tests/execution_core/test_protection.py tests/execution_core/test_protection_stateful.py tests/execution_core/test_import_boundary.py`: passed in 108.3 seconds; collection was exactly 449 + 35 + 27 = 511 tests.
- `ruff check .`: passed. Candidate Ruff format check: passed, 2 files already formatted. `mypy app --no-incremental`: passed, 86 source files. `lint-imports`: passed, 122 files / 621 dependencies / 6 contracts kept / 0 broken. Exact-delta `git diff --check`: passed.
- Projection/provenance trace: the count comes from the proof's execution checkpoint after lineage, proof-commitment, execution-commitment, and checkpoint-to-execution verification; the private projection factory retains it; the v2 projection commitment and authenticity recomputation bind it; pre-exposure provenance is state-committed and excluded from `_real_exit`. No public function/field, caller-authored flag, variable history, I/O, runtime, or deferred authority was added.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: the broader 1,254-test execution-core corpus was not rerun by this review seat because the requested 511-test gate was reproduced and the bounded live catch-up counterexample resolved the material determination. Python 3.11/3.12 exact-head CI, M2/runtime recovery fencing, persistence, database/SQL, broker/Alpaca, network, credentials, master merge, deletion, and cleanup remain outside this review and were not exercised.
