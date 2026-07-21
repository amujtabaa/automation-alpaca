# FINDING — W3 test-integrity defects (mutation-testing survivors)

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (REV-0023 Phase A, test-critic; 13 mutations run one-at-a-time against the full
  W3 suite at `f092ca7`, 10 killed, 3 survived + 2 partial survivors). Working tree verified
  restored; post-restoration baseline identical (410 passed, 3 xfailed).
- **Severity:** headline **P0 (test)** for TC-01; remainder P1–P3 as listed.
- **Cluster:** F2 in `work/review/REV-0023/phase-a.md`. Remediation: WO-0028 (DRAFT).

| ID | Sev | Defect | Evidence |
|----|-----|--------|----------|
| TC-01 | **P0** | `tests/test_wo0019_engine_seam.py:268-271` asserts reprice venue-targeting as `X or True` — a literal tautology. NO W3 test pins which venue order a reprice targets: mutating the venue replace to target `"totally-wrong-venue-order"` (app/reconciliation.py:536) survived the ENTIRE suite (410 passed, exit 0). On a real venue this replaces the WRONG live order and leaves the true working order resting — max-outstanding=1 broken at the venue. Fix is deleting `or True` (the assertion then reads exactly as intended). This is the X-002 *shape* (test weakened until green) on a live venue-safety surface. |
| TC-02 | **P1** | Ratchet monotonicity unpinned: `stop = max(stop, candidate)` → `stop = candidate` (app/sellside/trails.py:186) survived the entire suite. The grinder tape is too smooth to distinguish ratcheted from unratcheted stops. Needs an ATR-expansion-collapse tape where a later candidate sits strictly below an earlier one. |
| TC-04 | P2 | `tests/test_wo0019_engine_seam.py:199-203` uses `pytest.raises((OrderIntentBlockedError, Exception))` — catch-anything. Replacing the staging body with `raise KeyError("bug")` still passes. Fix: raise-set = the two refusals the docstring names. |
| TC-05 | P2 | Kill-race test's "approval landed first → FROZEN by hook" branch is structurally unreachable (hook deleted → 20/20 passes; gather+lock deterministically serialize kill first). H3 remains pinned only by the direct test (which DID kill the mutation). Force the ordering explicitly or drop the dead branch. |
| TC-06 | P3 | The hypothesis property's `replace_calls <= 4` leg is unreachable by its own generator (budget off-by-one survived 3/3 property runs; killed instantly by the targeted chaos test). Add a directed strategy or an exact drain script inside the property. |
| TC-07 | P3 | `assert status in (EXHAUSTED, FROZEN)` union in the exhausted-signal chaos test: single-mechanism mutations ARE killed; residual naming/precision nit only. |
| TC-08 | P3 | WO-0019a SDK client is a bare `Mock()`, not `create_autospec(TradingClient)`. Verified today: method names exist on alpaca-py 0.43.5 and the wrong-name mutation was killed — X-002 defeated *now*, but an SDK-upgrade rename would pass silently. |

Also discovered through this lens (filed separately as a P1 app defect):
FINDING-W3-memory-atomic-envelope-rollback.md (TC-03).

## Note for Phase B

Per protocol Phase A results are not shared with the Codex seat pre-verdict; but the human should
know that until TC-01 is fixed, "suite green" is NOT evidence on the replace-targeting surface.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by WO-0028.** TC-01 through TC-08 were strengthened or corrected without weakening a
test; the close-out records a 14/14 killed mutation matrix. Load-bearing pins include the exact
reprice-target assertion in `tests/test_wo0019_engine_seam.py`,
`test_ratchet_holds_when_atr_expands_and_candidates_collapse` in
`tests/test_wo0021_regime_tapes.py`, the four memory rollback pins, and the promoted
`tests/test_rev0023_phase_a_pins.py` corpus. The assembled W3 remediation review is
dispositioned RESOLVED in REV-0023, and AUDIT-0002 F009 independently reconciled this class as
fixed. **Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
