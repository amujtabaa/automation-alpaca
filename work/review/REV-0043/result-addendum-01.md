---
type: Review Result Addendum
rev_id: REV-0043
addendum: 01
title: "WO-0139 R5b-2 — re-review of the F-1/F-2 remediation"
reviewer_seat: Claude (independent review seat; implementer was Codex)
prior_verdict: ACCEPT-WITH-CHANGES
verdict: ACCEPT
re_review_head_sha: 330ca0a79f28f9a8894974e747996b30bccbe371
re_review_range: d540258..330ca0a
branch: codex/signal-r5b2-operator-auth
open_operator_decision: "F-4 — the detected_by \"conversion\" token (NEEDS-INPUT; must resolve before close-out)"
reviewed: 2026-07-25
---

# REV-0043 addendum 01 — remediation cleared, verdict ACCEPT

Reviewer-owned addendum; the original **ACCEPT-WITH-CHANGES** stands as the first-pass record. Scope,
as stated in `result.md`: **F-1, F-2, and the F-4 disposition** — not a full re-run. One commit
reviewed: `330ca0a fix(signal): remediate REV-0043 actor contracts`.

## F-1 and F-2 — CLEARED, and both proven decisive by the mutations that previously survived

Codex closed both with a **single parametrized pin** covering both routes and both findings:
`tests/test_recovery_actor_provenance.py::test_flag_off_recovery_routes_require_canonical_x_actor_header`
— asserting `422` **and** `("header", "X-Actor") in error_locations`. Review-seat mutation results:

| Mutation | Before remediation | After |
|---|---|---|
| **MUT-A (F-1)** — `/fills` **only** → `Depends(get_actor)` | survived the **entire full suite** | **1 failure** ✓ |
| **MUT-B (F-2)** — drop `alias="X-Actor"` from `get_required_actor` | nothing pinned it | **2 failures** (both parametrized cases) ✓ |
| baseline / restored | — | 0 failures ✓ |

`alias="X-Actor"` is restored at `app/api/deps.py:233`, and `get_actor` at `:209` is confirmed
**unchanged from master** (`x_actor: str | None = Header(default=None)`, no alias — master never had one
there), so the fix is targeted rather than broad.

The elegance is worth noting: one pin now guards the invariant-9 canonical-fill route's required-label
contract *and* the flag-off wire casing, on both routes. That is a better answer than the two separate
assertions `result.md` asked for.

## F-3, F-5, F-7 — all landed

- **F-3** — `tests/signal_seat_helpers.py:45` now pins `enable_dev_routes=True`, closing the unasserted
  precondition (the WO's claim that it already did so was mine and was wrong).
- **F-5** — `docs/spec/signal-seat/02-lifecycle.md` now reads "`GET`/facade reads **and existing-record
  ingest echoes (idempotent replay or duplicate conflict)** may return a copied record with effective
  status EXPIRED, but they do not change stored status and do not append `SIGNAL_EXPIRED`." Exactly the
  requested clause; the text now describes the code.
  *(Reviewer note: an initial truncated grep made this look absent. It was present; the tooling was at
  fault, not the work.)*
- **F-7** — `pkl/architecture/signal-seat.md` corrected: the stale "facade reads, operator enforcement,
  and lazy expiry remain R5b-2" is re-tensed to R5b-1's close, and R5b-2's delivered scope is recorded.

**F-6 and F-8** correctly recorded for R6 only. **F-4** correctly left `NEEDS-INPUT` — Codex did not
choose, which is right: it is not the implementer's decision.

## Gates reproduced by the review seat (POSIX, head `330ca0a`)

- R5b-2 corpus: **266 passed** (+2 from the new parametrized pin), exit 0, zero failures
- **Full suite: 100%, zero `FAILED`/`ERROR`** — verified to completion
- `ruff check .` → All checks passed · `mypy app/` → **77 source files**, no issues ·
  `lint-imports` → **6 kept, 0 broken**

*Method disclosure:* a first full-suite attempt timed out at 92% (wall-clock, zero failures) and an
earlier one reported a wrapper's exit code while pytest was at 9%. Neither was recorded as a pass; the
result above is from a run watched to completion on its real PID.

## Verdict

**ACCEPT.**

Both P2 defects are closed, and — the part that matters — each is now caught by the exact mutation that
previously survived. F-1 was the sharpest finding of this review: an inert pin on the route that ingests
a canonical fill (invariant 9), where the whole suite stayed green while the control was reverted. It is
now decisively held. F-2's flag-off wire contract is byte-restored. The three close-out items landed,
and the two register items were correctly deferred rather than absorbed.

**The REV-0043 review gate for WO-0139 is CLEARED**, subject to the one open operator decision below.

## ⚠ Open operator decision — F-4, required before close-out

`docs/spec/signal-seat/02-lifecycle.md:51` declares
`detected_by: "sweep" | "ingest" | "conversion"`. D-R5b2-18's ratified outcome authorized **removing**
`"read"`; adding `"conversion"` is a new **event-log payload vocabulary** value on a human-gated
surface, which the WO's own stop conditions bar. Nothing emits it today; conversion is R7's.

**Reviewer's position, disclosed:** the token faithfully encodes semantics the operator *did* ratify —
the D5 decision text names the durable writers as "the sweep, at ingest (dead-on-arrival), or atomically
inside the A-2 conversion command" — and I flagged the addition approvingly in review discussion before
weighing it against the stop condition. So it is a documentation-faithful encoding, not a new design
choice.

**Either resolution is defensible; it must simply be explicit:**
- **(a) Acknowledge the token** — cheapest, documents already-ratified semantics, and R7 later ships the
  emitter against text that already anticipates it.
- **(b) Revert to `"sweep" | "ingest"`** — strictest reading of the stop condition; R7 adds
  `"conversion"` together with the code that emits it, so vocabulary and emitter land in one reviewed
  change.

**Recommendation: (a).** The semantics are ratified, the token is inert until R7, and reverting would
leave the amended text describing only two of the three writers the operator explicitly named.

## Remaining before R6 (implementer/operator, not reviewer)

1. Resolve **F-4** (above).
2. Close out WO-0139 in one commit: `REVIEW` → terminal status, disposition
   `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`, `work/ledger.jsonl` line, move out of `work/active/`; both
   hygiene scripts green. (PKL is already refreshed per F-7.)
3. Write `work/review/REV-0043/disposition.md` recording the ACCEPT-WITH-CHANGES → ACCEPT sequence, F-1
   and F-2, the F-4 ruling, and **F-6 / F-8** carried to the R6 register.
4. Merge the branch and the planning branch to master.
5. **D-2a stays OFF.** Round 3 (R6 → gate → R7a) is next, and R6's WO-0104 refresh still needs its FULL
   war-game — including the unresolved **C-3 Protocol seam** (one `check_ingest` method cannot express
   the required step-4 atomic debit) and the allowed-paths defect that blocks
   `app/signals_rails_impl.py`.
