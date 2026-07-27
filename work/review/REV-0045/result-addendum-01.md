---
type: Review Result Addendum
rev_id: REV-0045
addendum: 01
title: "WO-0140 R6a-R truth-model remediation: second independent adversarial pass"
reviewer_seat: Codex (independent cross-model review seat)
base_sha: b48235e
head_sha: cb7a11e
verdict: BLOCK
delta_p0_count: 2
delta_p1_count: 0
cumulative_p0_count: 4
cumulative_p1_count: 3
reviewed: 2026-07-27
---

# REV-0045 addendum 01 — **BLOCK**

This disclosed second pass does not amend or replace `result.md`. It began with that result as a
hypothesis list, re-ran its decisive evidence, and then attacked release identity, tolerant recovery,
structural bounds, and composed memory/SQLite behavior. The original two P0s and three P1s reproduce.
Two additional P0s independently block the gate.

## New blocking findings

### P0-3 — an out-of-domain release carrier creates a dual-store startup and recovery divergence

- **Cause:** `sequence_from_release_dedupe_key` enforces positivity but not the ratified SQLite
  structural maximum. The strict zero-width fold therefore accepts a carrier that the memory store
  can retain as a Python integer but SQLite cannot bind to `signal_producer_rails`. The two release
  floors also judge an oversized logged number differently: memory retains the integer, while the
  SQLite JSON aggregate can expose it as a non-integer numeric value and omit it from the floor.
- **Impact:** The same append-only event history opens in memory but raises during SQLite
  `initialize()`. In a follow-on human-recovery composition, memory refuses the release while SQLite
  advances the carrier and releases. This is a fresh class-A dual-store divergence and directly
  satisfies REV-0045's stated BLOCK condition.
- **Affected files:** `app/events/projectors.py:1218-1254,1332-1346`,
  `app/store/memory.py:320-371`, `app/store/sqlite.py:1688-1745,1774-1817`.
- **Fix:** Parse a complete release identity against the expected producer; reject sequences outside
  `[1, 2**63-1]` before projection; make both floors apply the same typed structural rules; and make
  tolerant startup convert a structurally invalid producer history into one bounded per-producer
  marker rather than attempting an unbindable row write. Pin the exact maximum and the first
  out-of-domain value across strict replay, tolerant replay, memory, and SQLite.
- **Evidence:** A fresh minimal probe over one identical history produced
  `MEMORY_OPEN` with an out-of-domain carrier and `SQLITE_FAIL OverflowError`. A separate composed
  recovery probe produced `MEMORY ValueError` versus `SQLITE RELEASED`. No existing test failed on
  either composition.

### P0-4 — the poisoned-producer heal bypasses release exactness and the never-regress rule

- **Cause:** Once a producer is marked poisoned, `project_producer_rails_tolerant` accepts a release
  after checking only raw zero-width equality and whether its sequence component can be parsed. It
  bypasses the strict release checks for exact payload fields, actor validity, bounded counters,
  aware timestamps, producer/key binding, and monotonicity against `last_known`.
- **Impact:** A malformed human-recovery event clears the refusal marker, and a bounded but
  regressive release identity can replace a higher readable carrier with a lower one. Both stores
  and replay agree on the invalid healed state, so ordinary parity is green while the exactness
  ratchet and the operator-ratified never-regress rule are both violated. This is an unapproved
  weakening of human-gated event-log truth.
- **Affected files:** `app/events/projectors.py:1257-1347,1474-1518`;
  missing negative coverage in `tests/test_signal_rails_remediation.py:438-495,936-953`.
- **Fix:** Route every release, including the poisoned fast path, through one exact structural
  validator. For a poisoned heal, validate the closed payload, canonical producer-bound key,
  structural bounds, zero-width timestamps, and the required next sequence against the marker/log
  high-water value before clearing the marker. Add negative pins for each rejected class on strict
  replay, tolerant replay, memory, and SQLite.
- **Evidence:** Fresh direct and full-store probes showed an invalid-actor release clearing the
  marker on memory, SQLite, and replay. A second probe began with a readable higher carrier and ended
  clean at a lower carrier on all three paths. The focused rails corpus remained green.

## Expansion of original P1-1 (not double-counted)

The first result reported that the release-key parser ignores the producer component. The second pass
found two more branches of the same incomplete identity contract:

- a normal open-epoch release returns before parsing its dedupe identity at all; and
- the strict zero-width branch accepts any upward jump, although the ratified rule says it consumes
  the **next** sequence.

Affected code is `app/events/projectors.py:1290-1306,1332-1346`. Direct strict-fold probes accepted
both cases. The P1-1 fix therefore needs one producer-bound, structurally bounded identity parser
called for every release plus an exact-next assertion, not only validation of the first encoded part.

## Reproduction and mutation record

- Full prescribed Windows battery with a fresh OS-temp `--basetemp`: **FAIL**, exit 1. The same
  `test_ratified_cap_literals_are_single_sourced` path-normalization defect was the only failure.
  Exact branch coverage was **93.0532%**, so the coverage floor passed while the suite remained red.
- Flat state-seed mutant, independently re-applied in both stores: the named state-1/open-restart pin
  passed, and the entire five-module focused rails corpus (excluding only the already-red Windows
  source-scan test) also passed. Source was restored. P0-2 is confirmed.
- New memory/SQLite/replay compositions: malformed heal and regressive heal agreed on an invalid
  clean state; the structural-bound composition diverged across stores as described in P0-3.
- `ruff check .`: PASS. `mypy app`: PASS (77 files). `lint-imports`: PASS (6 kept).
  Changed Python files pass `ruff format --check`.
- Scope re-audit found no DDL/index, `app/server.py`, event payload field, or vocabulary-value
  addition. The existing-test edit set remains within the closed authorized list. These passes do
  not offset the P0s.

## Second-pass verdicts on all ten named items

| Item | Verdict | Second-pass result |
|---|---|---|
| 1. Pre-R6a corpora | PASS | Focused corpus still reproduces per-producer tolerance and replay poisoned-set parity. |
| 2. Debit folds nothing | PASS | Incremental debit and the no-rescan pin remain intact. |
| 3. State-conditional seed / anchor | **FAIL** | The flat-seed mutation again leaves both the named pin and focused corpus green; the memory anchor still scans globally. |
| 4. Zero-width release / refinements | **FAIL** | P0-3, P0-4, and expanded P1-1 show incomplete structural, producer, next-sequence, and poisoned-heal validation. |
| 5. Option-A release | **FAIL** | The nominal classified paths work, but recovery can accept malformed/regressive truth and a structural composition diverges across stores. |
| 6. Read-structural / write-capped | **FAIL** | The fold accepts a value outside the stated structural domain, and the required Windows source-scan pin remains red. |
| 7. `_atomic()` extension | PASS | Snapshot/restore coverage remains present; the new memory refusal rolled its in-transaction marker change back as designed. |
| 8. In-loop refutation passes | PASS, not independent credit | Disclosures remain adequate; the new P0s demonstrate why those passes could not clear the gate. |
| 9. Spec/ADR amendments | PASS | No new documentation drift was found in this pass. |
| 10. Process disclosures | PASS as disclosure only | The recorded defects remain candid; reproduced and new defects still prevent clearance. |

## REV-0044 addendum — R-1/R-2 gate status

**The R6a gate remains blocked. REV-0044 does not clear.**

- **R-1 remains open:** the named legacy fixtures open, but tolerant startup admits malformed
  recovery truth and an out-of-domain carrier bricks SQLite rather than isolating one producer.
- **R-2 remains open:** the debit path is incremental, but the memory anchor still performs a global
  scan and the required state-seed mutation proof is inert.

Keep D-2a OFF and R6b blocked. Corrections must return through a disclosed reviewer-owned addendum
with a fresh clean battery, failure-capable seed pin, bounded producer-bound release identity, strict
poisoned-heal validation, and dual-store recovery evidence.
