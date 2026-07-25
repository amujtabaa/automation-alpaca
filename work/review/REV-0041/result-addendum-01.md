---
type: Review Result Addendum
rev_id: REV-0041
addendum: 01
title: "WO-0137 R5a — re-review of the four ACCEPT-WITH-CHANGES follow-ups"
reviewer_seat: Claude (independent review seat; implementer was Codex)
prior_verdict: ACCEPT-WITH-CHANGES
verdict: ACCEPT
re_review_head_sha: b2a5667172a63c201ba7f3062a3a01a6a28018fb
re_review_range: d78e54fda6a780546cd6892078b209f9ae33438f..b2a5667172a63c201ba7f3062a3a01a6a28018fb
branch: codex/signal-r5a-foundation
human_gated_surfaces: [auth-launcher, transport-bind]
reviewed: 2026-07-24
---

# REV-0041 addendum 01 — follow-ups cleared, verdict ACCEPT

Reviewer-owned addendum (protocol: the reviewed party never edits `result.md` in place; corrections
and re-reviews are separate disclosed addenda). The original `result.md` verdict
(ACCEPT-WITH-CHANGES) stands as the record of the first pass; this addendum supersedes it with the
final verdict for the packet. The implementer did **not** modify or copy the reviewer-owned
`result.md` — confirmed absent from `codex/signal-r5a-foundation`.

Re-reviewed range: `d78e54f..b2a5667` — one implementer commit,
`b2a5667 fix(signal): resolve REV-0041 follow-ups`, touching 5 files
(`app/config.py`, `tests/test_signal_seat_config.py`, `tests/test_signal_seat_launch_guard.py`,
`work/active/SIGNAL-R5a-STATE.md`, the WO). The frozen `request.md` was not altered by that commit.

## Follow-up verification

| Item | Required change | Verdict | Independent evidence (this review) |
|---|---|---|---|
| **C-1** | Isolate the inert exact-type pin so `launch_guard.py:158` is the decisive control | **CLEARED** | `tests/test_signal_seat_launch_guard.py:117-140` now mints the subtype with the real `_MINT_TOKEN` and **registers it under its own identity**, so the `:162` identity check passes and only exact-type can reject. **Red-green: the identical mutation (`:158` → `isinstance`) that previously left this pin GREEN now turns it RED; restored → GREEN.** `finally` block restores registry state; verified no leakage (guard file run twice in one session → 18 passed) |
| **C-2** | Exact-`str` for `signal_transport_policy` + test coverage | **CLEARED** | `app/config.py:490` is now `type(settings.signal_transport_policy) is not str`. New 4th parametrized case `[transport-policy]` injects a `str` subclass carrying a *valid* policy value, so only exact-type can reject it. **Red-green: reverting `:490` → `isinstance` turns `[transport-policy]` RED; restored → GREEN.** Test renamed `..._credentials` → `..._config_values` (scope-accurate) |
| **C-3** | Qualify `red_green_verified` as live-control verification | **CLEARED** | `SIGNAL-R5a-STATE.md:275,287` add `verification: "live-control (regression committed d78e54f)"` to exactly the two capability-hardening blocks (attempts 2 and 3) flagged in `result.md` C-3. Correctly targeted — the other FIX blocks, whose RED was a genuine committed-test or tooling failure, are untouched |
| **C-4** | Enumerate the full authorized-edit surface, not "three edits" | **CLEARED** | WO `:286-297` enumerates all five classes: D-R5a-1/-10 (additive import-boundary hunk), D-R5a-3 (transport vocabulary), D1 (launcher child-env + timeout), D2 (explicit test authority + rejection coverage), D-R5a-4/-7 + Part B (additive capability/config regressions). `:276-278` cross-references it from the no-weakening rule |
| **R5b-N1** | Record only — exact-`dict` producer map at the request-time auth seam | **CLEARED** | WO `:299-300+` records the carry-forward requirement explicitly as "record only; not implemented in R5a". No R5b code added (scope re-confirmed below) |

## Gates independently reproduced (this review, POSIX, head `b2a5667`)

- `ruff check .` → **All checks passed!**
- `ruff format --check` on the 11 R5a-owned files → **11 files already formatted**
- `mypy app/` → **Success: no issues found in 74 source files**
- `lint-imports` → **Contracts: 6 kept, 0 broken**
- R5a corpus + import boundaries → **57 passed** (config 24 incl. the new case, launcher 9, guard 18,
  import-boundary 6) — matches the author's 57/57
- R2 conformance oracle via the CI module invocation → **61 passed**
- Full suite → **exit 0, zero `FAILED`/`ERROR` lines, progress 100%**

Disclosure on precision: I confirmed the full suite by **exit code, zero failure lines, and 100%
progress**, not by transcribing a total-count line (this environment's `-q` summary line was not
recoverable from the captured log). The author's "4,328 collected" figure is therefore corroborated
as *green*, not digit-for-digit. Every other number above I measured directly.

## Scope re-confirmation

The follow-up commit adds **no** R5b/R6/R7 surface: no routes/middleware/deps/schemas/cockpit, no
`.importlinter` change, no schema/event-log/ledger touch, no flag enablement. The only production
change in the range is the one-line `app/config.py:490` type check. WO-0137 remains `REVIEW`; no
disposition, ledger line, file move, merge, PR, or close-out occurred — correct, those belong to
close-out.

## One non-blocking merge-time reconciliation

WO `:168-172` records that `work/queue/SIGNAL-R5a-NEEDS-INPUT-DISPOSITION.md` "is absent from both
the confirmed `4bb1bfb` base and fetched `origin/codex/signal-r5a-foundation`", and treats the
operator-relayed instruction as the disposition authority. That was **accurate** for the implementer's
checkout — the planning seat committed that file to
`claude/signal-r4-kickoff-planning-354qc0` (`0c71745`), not to the implementer branch. The two
branches carry complementary halves of this packet and do not conflict:

- planning branch → `SIGNAL-R5a-NEEDS-INPUT-DISPOSITION.md`, `REV-0041/result.md`, this addendum;
- implementer branch → `REV-0041/request.md`, the implementation, WO/state.

After both merge to master, the "absent" note becomes stale. **Close-out should reconcile that
sentence** to cite the disposition file by path. Documentation-accuracy only; it does not affect the
security boundary, the evidence, or this verdict.

## Verdict

**ACCEPT.**

All four ACCEPT-WITH-CHANGES follow-ups are cleared, and the two that mattered behaviorally (C-1,
C-2) are confirmed **decisive by red-green proof**, not merely present. C-1 is the material result:
the pin that was inert at the first pass now fails under the exact mutation it previously survived,
so the exact-type control is genuinely pinned rather than only redundantly protected.

The R5a construction-time launch/capability boundary was found sound at the first pass (nine
properties verified under static trace and live execution across three independent verifications) and
nothing in this range weakens it. Scope stays confined; the feature flag stays OFF.

**The REV-0041 review gate for WO-0137 is CLEARED** (`ACCEPT`), satisfying the CLAUDE.md requirement
that a human-gated-surface change's gate clears only on a dispositioned `ACCEPT`/
`ACCEPT-WITH-CHANGES` packet.

Remaining before this foundation is relied upon — implementer/operator, not reviewer:
1. Close-out in one commit: `REVIEW` → terminal status, disposition
   `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`, `work/ledger.jsonl` line, move the WO out of `work/active/`,
   signal-seat PKL R5a changelog; `check_work_order_disposition.py` + `check_ledger.py` green.
2. Merge both branches to master (order-independent; complementary files).
3. Reconcile the WO's "disposition file absent" sentence (above).
4. The unnumbered formatter-baseline cleanup WO (10 inherited files) remains follow-up work.
5. D-2a unchanged: the flag flips only when R5b + R6 + R7 also close. R5b inherits R5b-N1.
