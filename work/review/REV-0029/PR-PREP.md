# PR prep — assembled AFTER REV-0029 ACCEPT (H.2: the human merges, never the agent)

## Master divergence (read-only check, 2026-07-17, HEAD `f083222`)

- `origin/master` tip: `2aa377a` (the PR #8 merge). Merge-base with our trunk: `22617f4` — i.e.
  master's only CONTENT ahead of us is **`38762a1`** ("tests: defuse the tape-clock time bombs",
  fixture-only).
- `git merge-tree --write-tree HEAD origin/master` → **conflicts in exactly 3 TEST files** (both
  sides fixture-only and semantically independent: master's tape-clock defusals vs this branch's
  R2/Option-B fixture work): `tests/test_wo0020_envelope_tick.py`,
  `tests/test_wo0021_envelope_chaos.py`, `tests/test_wo0025_multileg.py`. Zero production-code
  conflicts. Resolution at PR time is mechanical (take both edits); NO rebase before the review
  gate clears (plan §4-F9 — history stays stable under review).
- PR #7 (signal-seat) rebases after this lands (pre-existing obligation, §G.5/H.2).

## Draft PR body (fill SHAs at assembly)

---

**Title:** R2 consolidation: canonical SellIntent↔Envelope lifecycle link (WO-0036 / WO-0105 / WO-0107)

**Summary.** Consolidates the two independent WO-0036 R2 implementations into one canonical,
safety-preserving trunk per the CAMPAIGN-0002 charter: Sol's delegation-projection mechanism
(ratified I.1) + an indexed projection precondition (I.2) + the Claude attempt's grafts (F.2) +
the Option B atomic flatten (WO-0107) + the two cross-investigator spec properties (session-close
sparing, needs-review retention), with the four planes reconciled (code / docs / planning /
architecture).

**Safety surfaces touched (all operator-ratified, all independently reviewed via REV-0029):**
order-intent lifecycle, session-close event truth, manual flatten. Invariants: INV-090 added;
INV-081/037/052 amended; INV-032/036/080/087 re-verified. ADR-010 amended §3/§4/§6.

**Evidence.** Full suite 3058+/0/0 (+ coverage gate); both spec oracles green (Codex 61/0
explicit; Claude 22/6 recorded NEEDS-INPUT skips, unmodified since Part A); perf gates
structural-green with two pre-existing marginal wall-clock misses recorded as a named finding
(baseline-proven, no regression from this work). Independent cross-model review: REV-0029
ACCEPT[-WITH-CHANGES] (packet + disposition in `work/review/REV-0029/`).

**Open by design:** PD-1 needs-review release valve (parked decision, `BLOCKED-DECISIONS.md`);
backfill verification pre-beta (D5); perf follow-up WO candidate (P4).

---
