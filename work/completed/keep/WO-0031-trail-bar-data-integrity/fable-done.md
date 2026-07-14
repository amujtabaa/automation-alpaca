# WO-0031 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0031]

Approved in-chat ("Yes on the batch"); item (c) adjudicated by Ameen same day
(incumbent-behavior-but-REPORTED + dynamic min-size upsize + Alpaca research).

## done_when → met

1. **(a) SOL-F-002 — lifetime-monotone working stop.** `compute_working_stop`
   gains `urgency_at` (historical prefixes keep their OWN epoch's urgency)
   and `last_bar_open` (the mutable open bucket never enters the ratchet;
   reporting still reflects the full tape at current urgency). `decide` wires
   both via the new pure `_urgency_at`. Pins flipped/rewritten to the
   lifetime framing, incl. a kept regression line documenting the OLD
   loosening behavior. Frozen decide() signature untouched.
2. **(b) SOL-F-003 — whole-tape screening.** Every tape row is screened by
   `_snapshot_invalid_reasons` before ANY feature computation; invalid
   history is dropped (latest-row disposition gate unchanged). Pin is
   decide-level (poisoned $30 stale+crossed print changes nothing).
3. **(c) SOL-F-004 + adjudication.** The zero-allowance protective probe
   stays ("protection beats participation politeness") but now carries a
   participation ClampNote, and `_rejected_probe_count` doubles the probe
   floor after each venue-REJECTED probe (capped by remaining) — the
   min-order-size armor Ameen requested. Both pinned.
4. **(d) DRIFT-SVD-2.** The tranche latch counts WORKING actions only;
   a refused_stale event (provenance keeps the tranche flag) no longer burns
   the entitlement. Pinned with a positive control (a real tranche submit
   still consumes exactly once). core.py untouched — policy-side filter.
5. **Mutation-checks 6/6 KILLED** (each mechanism individually). Full gate
   green: ruff/format, mypy 64 files, imports 6-0, pytest exit 0, zero
   FAILED. INV-086 registered.

## Incident (visible — and copied to W3-STATE per the new doc-13 rule)

The FIRST version of the SOLF3 pin was VACUOUSLY green: its tape priced
below the envelope floor, so clean and poisoned runs both returned
BreachSignal(floor) and compared equal — screening on or off. Caught by this
WO's own R4 discovery-mutation sweep (MC-3 survivor investigated, not
shrugged off), pin de-vacuized (price scale above floor), MC-3 re-run KILLED.
Lesson instance of the invariant-frame rule: an assertion that cannot
distinguish the mechanism's presence is not a test.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
