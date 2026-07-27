---
type: Review Result
rev_id: REV-0045
title: "WO-0140 R6a-R truth-model remediation: independent gate-clearing review"
reviewer_seat: Codex (independent cross-model review seat)
implementer: Claude (operator-confirmed seat swap)
base_sha: b48235e
head_sha: cb7a11e
verdict: BLOCK
p0_count: 2
p1_count: 3
reviewed: 2026-07-27
---

# REV-0045 — **BLOCK**

Independent review of `b48235e..cb7a11e`. The R6a gate does **not** clear.
The legacy-tolerance and live/replay behavior were substantially reproduced, but two P0s invalidate
the claimed green evidence and the decisive flat-seed mutation. Three P1s also remain.

## Blocking findings

### P0-1 — the claimed full battery is red on the required Windows checkout

- **Cause:** `test_ratified_cap_literals_are_single_sourced` builds a relative path with
  `str(Path(...))` but compares it to the slash-separated literal `app/models.py`.
- **Impact:** On Windows, the canonical cap declarations are falsely reported as out-of-place. The
  full battery cannot reproduce its green claim, so its completion evidence cannot clear a gate.
- **Affected files:** `tests/test_signal_rails_remediation.py:586-602`.
- **Fix:** Normalize the relative path before comparing it (or compare `Path` objects), then rerun
  the entire required battery with coverage.
- **Evidence:** Fresh prescribed battery, isolated under OS temp, exited **1** with this one test
  failing. Its exact branch coverage was **93.0583%** (above the floor, but the suite is not green).
  The claimed exact `93.0430%` therefore did not reproduce.

### P0-2 — the state-conditional seed mutation is now inert

- **Cause:** A flat seed makes a healthy open epoch fail the bounded fold, but the release path
  catches that failure and Option A reclassifies the same log to the normal release result. The pin
  observes only the final result and never asserts that healthy state-1 verification avoided the
  fallback.
- **Impact:** The rev-3 state-conditional-seed proof is no longer a failure-capable guard. A stated
  decisive mutation can regress in both stores without any focused rails test failing.
- **Affected files:** `app/store/memory.py:408-410`, `app/store/sqlite.py:1607-1609`,
  `tests/test_signal_rails_remediation.py:344-385`.
- **Fix:** Add a behavioral assertion that the healthy state-1 and open-restart paths do not enter
  drift poisoning/reclassification, and retain a mutation check that turns red with the subtraction
  removed.
- **Evidence:** I removed the open-epoch subtraction in both stores. The named pin passed; then the
  entire focused rails corpus (all five R6a modules, excluding only P0-1's already-failing Windows
  source-scan test) also passed. Source was restored and `git status --short` returned clean.

## Important findings

### P1-1 — the release-key parser accepts a malformed producer segment

- **Cause:** `sequence_from_release_dedupe_key` checks only the second, sequence-bearing component;
  it does not validate the first length-prefixed producer component or bind it to the event producer.
- **Impact:** A malformed release key can be accepted by the strict fold as consuming an epoch
  sequence, despite the ratified key structure and the later exact-key anchor. This creates an
  inconsistent carrier that is discovered only at a later boundary instead of being rejected at
  replay/startup.
- **Affected files:** `app/events/projectors.py:1218-1254`,
  `tests/test_signal_rails_remediation.py:936-953`.
- **Fix:** Validate both encoded key components and require the producer component to agree with the
  event's producer before using the sequence; add negative pins for malformed and mismatched producer
  components.
- **Evidence:** A local strict-fold probe accepted a release whose first key component was malformed
  and produced a normal sequence-bearing rail state. The existing parser pin covers only malformed
  sequence components and part counts.

### P1-2 — the in-memory O(1) anchor scans the global event log

- **Cause:** The in-memory anchor uses `any(... for event in self._execution_events)` instead of the
  existing dedupe-key map.
- **Impact:** It violates WO-0140's explicit exact-key, no-scan O(1) anchor rule and adds a third
  global scan while the single-writer lock is held on boundary/release work.
- **Affected files:** `app/store/memory.py:468-486`.
- **Fix:** Check both expected keys through the in-memory dedupe index and add a no-scan pin for that
  anchor path, matching SQLite's keyed lookup.
- **Evidence:** Source inspection shows a full-list generator at the anchor; the SQLite counterpart
  uses a direct dedupe-key query at `app/store/sqlite.py:1666-1685`.

### P1-3 — unrelated recorder formatting is scope creep

- **Cause:** The remediation diff includes ruff-only formatting changes outside the signal-seat
  scope.
- **Impact:** It adds unrelated review and merge surface to a human-gated remediation.
- **Affected files:** `app/recorder/__init__.py`, `app/recorder/models.py`, and
  `app/recorder/store.py`.
- **Fix:** Revert these unrelated formatting hunks or obtain explicit scope authorization.
- **Evidence:** `git diff b48235e..HEAD` shows only formatting changes in these recorder files;
  neither the work order nor its allowed paths names the recorder package.

## Named review items

| Item | Verdict | Independent result |
|---|---|---|
| 1. Pre-R6a corpora | PASS | The two corpus tests, replay poisoned-set parity, and unaffected-producer test passed in the focused rails run. |
| 2. Debit folds nothing | PASS | The no-rescan debit pin passed; the live debit path updates cached class-A state directly. |
| 3. State-conditional seed and O(1) anchor | **FAIL** | P0-2 makes the stated seed mutation inert; P1-2 shows the memory anchor is not O(1). |
| 4. Zero-width release and refinements | **FAIL** | The log-floor refinement is faithful and its floor-blind mutant is live; the parser refinement is incomplete (P1-1), so the whole item does not clear. |
| 5. Option-A log-classified release | PASS | SQLite and memory open-log classification mutants both turned RED; the custom dual-store parity composition passed. |
| 6. Read-structural/write-capped | **FAIL** | Behavioral cap pins are live, but the required single-source cap pin fails on Windows (P0-1). |
| 7. `_atomic()` extension | PASS | The rollback pin passed; both snapshot and restore include the poisoned-marker map. |
| 8. In-loop refutation passes | PASS, not credited as independent review | Disclosures and their live pins were inspected, but they do not replace this seat; P0-2 is a fresh regression after those passes. |
| 9. Spec/ADR amendments | PASS | ADR-009 and lifecycle text record the ratified no-epoch heal and repair-and-refuse semantics without adding a payload field. |
| 10. Process disclosures | PASS as disclosure, not as clearance | The three disclosed process defects were recorded candidly. The unreproduced green battery and inert mutation require corrective evidence before clearance. |

## Reproduction record

- Full prescribed battery: **FAIL**, exit 1; only P0-1 failed; branch coverage **93.0583%**.
- Focused rails corpus excluding only P0-1: **PASS**.
- Fresh dual-store composition selected by this review: **PASS** for live-vs-replay class-A state and
  poisoned-set agreement through debit, state-1 release, and resume on memory and SQLite.
- Mutants that remained live: widened zero-width acceptance, wrapper-heal removal, release-key-floor
  blindness, cap revalidation, Option-A classification blindness, exception narrowing, and removal of
  the at-limit gate all turned their targeted pins RED.
- Mutant that stayed green: flat state seed in both stores — P0-2.
- `ruff check .`: PASS. `mypy app`: PASS (77 files). `lint-imports`: PASS (6 kept).
  Changed Python files pass `ruff format --check`; repository-wide format remains red on seven
  unrelated pre-existing files.
- Static scope audit: no `app/server.py`, schema/index, event-type, or payload-field/vocabulary change
  was found; the authorized existing-test edits otherwise remained within the named pin work.

## REV-0044 addendum — R-1/R-2 gate status

**Gate does not clear.** REV-0044 remains **ACCEPT-WITH-CHANGES**.

- **R-1:** legacy tolerant-startup behavior is reproduced functionally, but it is not formally
  dispositioned because the required clean battery is red (P0-1).
- **R-2:** does not clear. Ordinary debit no longer folds, but the in-memory exact-key anchor still
  rescans the global log (P1-2), and the required state-seed mutation proof is inert (P0-2).

Keep D-2a OFF and R6b blocked. Corrections must return as disclosed addenda for a fresh independent
review; do not amend this reviewer-owned result in place.
