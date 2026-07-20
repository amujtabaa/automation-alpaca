---
type: Review Result
rev_id: REV-0031
status: COMPLETE
reviewer: Codex
reviewed_range: 7194f02..4d607da
reviewed_at: 2026-07-19
verdict: ACCEPT-WITH-CHANGES
---

# REV-0031 result — WO-0111

## Findings

### P1 — the no-stacking pins observe a set, so a second durable grant survives the test

- **Evidence:** `tests/test_wo0111_pr9_review_round2.py:186-198` and
  `tests/test_spine_phase3e_manual_flatten.py:175-177` assert
  `list_emergency_reduce_overrides() == {"AAPL"}`. The projection at
  `app/events/projectors.py:404-429` is latest-wins per symbol and returns a set, so one grant event
  and two consecutive grant events have the same result.
- **Concrete failing sequence:** authorize twice with the reviewed active-grant `return` neutered so
  execution falls through and appends a second `EMERGENCY_REDUCE_OVERRIDE`. On memory and SQLite,
  both changed tests remained green while the raw event log contained two grant events. The old
  raise mutation does turn them red, but it is not the mutation for the claimed "never stacked"
  property.
- **Why it matters:** the append-only audit truth can stack even while the derived active-symbol set
  looks correct; the stated guard-removal evidence and "strengthened" pin do not prove the property.
- **Resolution:** assert exactly one raw grant event for the current `{session, symbol}` before and
  after reauthorization, and exactly one resolve event after the authorized flatten, on both stores
  and on the real fail-closed/retry trajectory.

### P1 — active-grant precondition rechecks are correct but not load-bearing in tests

- **Evidence:** the implementation correctly checks `HALTED`, a positive position, and same-symbol
  `TIMEOUT_QUARANTINE` before the active-grant return at `app/store/memory.py:4615-4649` and
  `app/store/sqlite.py:6407-6446`. The changed test keeps all three conditions valid. Existing
  precondition tests at `tests/test_spine_phase3e_manual_flatten.py:223-258` exercise only the
  no-active-grant path.
- **Concrete failing sequence:** move the active-grant return above the three guards. The changed pin
  and the existing not-halted/flat/quarantine tests all remain green on both stores. A valid grant
  followed by clearing the halt then permits reauthorization in `ACTIVE` under the mutation.
- **Why it matters:** a future refactor can bypass every ADR-003 recheck without a safety pin
  failing.
- **Resolution:** grant while all preconditions are valid, independently invalidate trading state,
  position, and quarantine state, then require reauthorization to raise and append no grant. The
  exact test must fail when the reuse return is moved above any guard.

### P1 — a fill first recorded without envelope attribution cannot be repaired on replay

- **Evidence:** the monitoring bridge deliberately continues to `append_fill` after a
  `record_envelope_fill` failure (`app/monitoring.py:2297-2316`). Both use the canonical
  `fill:{order_id}:{source_fill_id}` dedupe identity. On replay, `record_envelope_fill` sees that
  existing FILL and returns before decrementing the envelope (`app/store/memory.py:1840-1841`,
  `app/store/sqlite.py:3069-3074`).
- **Concrete failing sequence:** create a supersession successor and its submitted child; record its
  broker fill first through `append_fill` (the persistent state the pre-fix disown bug could create),
  then replay the same broker update after lineage resolution works. Both stores observed:

  ```text
  remaining_before=100 remaining_after=100 position=90
  fill_events=1 fill_event_envelope=None
  ```

- **Why it matters:** WO-0111 prevents a new successor-disown event but does not repair a state
  already produced by that bug, nor a future transient bridge exception. Position truth advances
  while the envelope remains permanently armed for the already-executed quantity.
- **Resolution:** preserve append-only position truth and add an independently deduped,
  non-position-folding envelope-attribution/application marker. An existing canonical FILL with no
  envelope may be applied to exactly one uniquely validated envelope once; an existing FILL owned by
  another envelope must fail closed. Mutating the original FILL in place is not acceptable.

### P1 — an ordinary flatten can consume the surviving emergency grant

- **Evidence:** both facade commands share `_flatten_cancelling_open_buys`
  (`app/facade/store_backed.py:835,1064-1075`), and both stores treat any active symbol grant as
  authorization (`app/store/memory.py:2941-2963,2984-2991`,
  `app/store/sqlite.py:4314-4336,4355-4358`).
- **Concrete failing sequence:** a halted emergency reduce fails closed on a venue-uncertain BUY and
  leaves its grant active; after the BUY becomes terminal, call the ordinary `create_exit` command.
  On both stores the ordinary command minted a MANUAL_FLATTEN SELL and consumed the grant while the
  session remained halted.
- **Why it matters:** an ordinary command can steal the one-shot authority from the documented
  emergency retry. The behavior predates WO-0111 and is not a regression in this range, but the
  reviewed change deliberately preserves the active-grant window and the packet explicitly requires
  its consumers to be enumerated.
- **Resolution:** bind grant observation/consumption to an explicit internal emergency capability or
  store operation; an ordinary flatten must ignore an active grant and remain denied under `HALTED`.

## Closure-by-property

- **Parent classification:** `_owner_scoped` retains parent `E`, `None`, and fabricated/unknown
  parents through parent/correlation/referenced-owner/co-order discovery, and excludes only a known
  distinct envelope (`app/monitoring.py:562-584`). A known-parent scope conflict remains diagnosed by
  the shared projector (`app/store/core.py:1214-1232,1395-1411`) and the symbol projection.
- **Store projection parity:** a single `envelope_id` store projection is strict-parent scoped in
  memory (`app/store/memory.py:1089-1092`) and SQLite (`app/store/sqlite.py:1965-1973`); owner/intent
  projections include the whole lineage. Neither reproduces the monitoring one-envelope/owner-set
  mismatch.
- **Exactly-once nominal path:** one parent is selected at `app/monitoring.py:649-675`, and the
  canonical record-first bridge dedupes repeat polls. The fresh probe left predecessor remaining at
  100, successor at 90, position at 90, and one successor-attributed FILL event on both stores.
- **Authorization integrity:** all ADR-003 preconditions are presently ordered before reuse; the
  store lock serializes grant observation, flatten mint, and consumption. The nominal retry probe
  produced one grant, one exit, and one resolve on both stores.
- **Traceability:** every production/test line in `7194f02..4d607da` traces to the two WO-0111
  findings or their close-out. No unrelated behavior drift was found.

## Fresh probes and commands

```text
.\.venv\Scripts\python.exe -m pytest -q \
  tests/test_wo0111_pr9_review_round2.py \
  tests/test_wo0112_pr9_review_round3.py
.......... [100%]
exit 0
```

The packet's two new end-to-end scenarios were run through an inline async harness
(`.\.venv\Scripts\python.exe -`) against fresh `InMemoryStateStore` and
`SqliteStateStore` instances:

```text
fill attribution (memory/sqlite): predecessor_remaining=100,
  successor_remaining=90, position=90, fill_events=1 — PASS
retry after fail-closed (memory/sqlite): first_call=409, grant_events=1,
  BUY reconciled CANCELED, retry minted one MANUAL_FLATTEN, resolve_events=1 — PASS
```

Additional hostile probes:

```text
fall-through no-stack mutation: both changed pins PASS with grant_events=2 — MUTATION SURVIVED
early active-return mutation: changed + legacy precondition pins PASS — MUTATION SURVIVED
known-sibling exclusion neutered: exact F1 pin red on memory and SQLite
old active-grant raise restored: both F2 pins red on memory and SQLite
unattributed-fill replay (memory/sqlite): remaining 100 -> 100, position=90,
  one FILL with envelope=None — FAILURE CONFIRMED
git diff --check 7194f02..4d607da — exit 0
```

`pytest` was initially unavailable on ambient `PATH`; all recorded Python/test evidence therefore
uses the repository's `.venv\Scripts\python.exe` explicitly.

## Verdict

**ACCEPT-WITH-CHANGES.** The two reviewed production branches fix their nominal bugs and the packet's
fresh scenarios pass on both stores. The change set still has two non-load-bearing safety pins, an
irreparable missed-attribution state, and an unbound surviving-grant consumer. Full repository gates,
performance gates, and PR CI were not run during this packet review.
