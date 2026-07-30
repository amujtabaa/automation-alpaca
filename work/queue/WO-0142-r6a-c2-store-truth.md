---
type: Work Order
title: "R6a-C2 — store-side truth: append binding, persisted-cache discipline, replay parity"
status: DRAFT
work_order_id: WO-0142
program: work/queue/R6A-CONSOLIDATION-PROGRAM.md (WO-B of A/B/C)
parent: WO-0104a (REVIEW); WO-0141R (ACTIVE)
branch: TBD — not started
model_tier: strong (LOCAL — event-log truth, store rebuild path, human-gated write refusal)
seat: "CONDITIONAL on the REV-0045 round-4 verdict — ratified D-9(b), 2026-07-29. A DIFFERENT seat takes this WO if round 4 returns any finding-bearing verdict; the Claude seat that authored WO-0141R continues only on a clean ACCEPT. Rationale as put to the operator: this WO's central question is reversing WO-0140's ratified never-regress rule, and that seat's last two unilateral semantics rulings produced P0-6 and P0-7. Resolve this line before starting — an unresolved seat assignment is not a licence for whoever reads the file first."
review: "Codex-owned REV packet. Not this seat's gate to clear."
filter_risk: MED
---

# WO-0142 — R6a-C2: store-side truth

> **Why this file exists at all.** Two open defects and several carry-forwards were "routed to
> WO-0142" while no such file existed. An independent merge-readiness assessment named that: a
> defect routed to a work order that does not exist is a defect with nowhere to go, and the
> routing reads as disposition without being it. This is a DRAFT — not ratified, not started —
> but it is a real destination.

## Inherited obligations

| Item | Source | What it needs |
|---|---|---|
| **P0-8** — a durable rail row can hold a value no log fold produces | WO-0141R self-review; `tests/test_wo0141_persisted_carrier_divergence.py` (strict xfail) | Stop persisting `max(prior_row, marker.last_known_epoch_sequence)`. The row is a cache; **INV-099** says a cache may not exceed the truth it caches. Reverses WO-0140's ratified never-regress rule ⇒ needs its own ratification. |
| **D-1-b** — append-time binding validation | ADR-016 §1 (ratified, sequenced here) | Refuse at append any `PRODUCER_*` whose key-embedded producer ≠ payload producer, making new mismatches unrepresentable rather than merely handled. Needs a legacy-log story; D-1-a already covers reading them. |
| **Replay-vs-live for producer rails** | merge-readiness assessment | The comparator was extended to carry `invalid_projection_markers` but nothing exercises it end-to-end for rails. Either pin it or state plainly that it is unverified. |
| **REV-0044 R-1 caveat** | REV-0044 addendum-01 | Confirmed NOT discharged by round 3. Must be discharged or explicitly carried at WO-0104a's close-out, not this one. |
| **The release mint holds the write lock for O(log-length)** | WO-0141R measured assessment 2026-07-29; `request-round-4.md` §8a | `_next_release_sequence_locked` reads `SELECT * FROM execution_events ORDER BY sequence` — the whole log — materializes every row and folds it twice, under `self._lock`. Measured ≈31 µs/event end-to-end: 3.1 s at 100k events, ≈31 s extrapolated at 1M, serializing every other write including order submission. Not a correctness defect and not urgent (human release path only, and `initialize()` already folds the whole log on open), but unpinned by any scaling gate. **The obvious fix is a trap.** A `WHERE event_type IN (...)` pre-filter is the same *shape* as the payload pre-filter whose removal WAS the P0-3 fix, and the fold also consumes attributable signal events, so the enumeration is wider than inspection suggests. Needs the F-1 treatment — a machine-checked, build-failing enumeration — plus a scaling pin, not an inspection. Precedent: WO-0140 slice 3 closed this identical shape on the debit path with an incremental debit. |

## Open questions for the decision block (do not decide these while drafting)

1. **Never-regress reversal.** P0-8's repair contradicts a ratified WO-0140 rule. What did
   never-regress protect that log-derived minting does not already protect? WO-0141R removed the
   mint's dependency on the row, which may have made the rule vestigial — but "may have" is not an
   argument, and this seat's last two unilateral semantics rulings produced P0-6 and P0-7.
2. **Migration.** Does an existing database need its rail rows rewritten, or is recomputation on
   open sufficient? If rewritten, that is a schema/migration surface — human-gated.
3. **Scope budget under the amended P-3.** A limb is counted where a derived quantity is CONSUMED.
   Score this before proposing it, not after.

## Out of scope

Everything R6b: `/api/producers`, the release route, cockpit controls, sweeps, rate settings, and
flipping `SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE` (INV-100). Those are WO-0104b.
