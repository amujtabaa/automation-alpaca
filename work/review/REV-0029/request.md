# REV-0029 — request: the consolidated WO-0036 R2 Part B (independent cross-model review)

> **The single independent review gate for the R2 consolidation.** Per `CLAUDE.md` and the
> campaign charter, every human-gated surface this work touched (order-intent lifecycle,
> session-close event truth, manual flatten, ADR amendments) clears its review gate ONLY on this
> packet's `ACCEPT` / `ACCEPT-WITH-CHANGES` verdict + a recorded disposition loop. Per operator
> ratification **D4** this packet **subsumes REV-0024** (WO-0107 Option B — its request survives
> at `work/review/REV-0024/` for context) and **supersedes REV-0028** (the Claude-attempt packet,
> never dispositioned, attempt branch only). In-process review passes (below) do NOT count.

## Scope

- **Branch:** `consolidate/r2-canonical`. **Review diff:** `5d10c70..HEAD` (~20 commits: Sol
  mechanism port + indexed projection, R6 logging, WO-0107 Option B, and the Part B completion
  run P1–P7). Freeze anchors for comparison: `22617f4` (pre-R2 base), `ba1cea7` (Claude attempt),
  `353ef1c` (Sol attempt).
- **Authority chain:** Part A report (`../CAMPAIGN-0002-claude/report.md`) → operator
  ratifications (`RATIFICATION-part-a.md`, `RATIFICATION-partb-completion.md` D1–D9) →
  `PARTB-COMPLETION-PLAN.md` (the executed plan + §6 evidence log).

## Turnkey verification (run all; every one green at `f083222`)

```
ruff check . && ruff format --check . && mypy app/ && lint-imports
pytest -q                                        # full default suite (+ coverage gate in CI form)
pytest -q tests/r2_conformance_oracle.py         # Codex spec oracle — NOT default-collected
pytest -q tests/test_r2_conformance_oracle_claude.py   # Claude spec oracle (6 NEEDS-INPUT skips)
python -m tests.performance.r2_scaling_gate      # exits 1 — see the P4 finding below
```

## What to review (lenses, most important first)

1. **The treadmill-sibling-class walk (charter §3, fresh-eyes-on-merged-diff mandate — you are
   the "different reviewer than the builder").** Assert closure of each class BY PROPERTY, not by
   the instance test that pins it: masked-predecessor (five choke points), release-while-child-
   rests, orphan-at-close, double-mandate, blind-resubmit/blind-cancel, stale-read flatten
   (§5.3), needs-review second-sell.
2. **The three retention predicates** (`project_envelope_obligation`, `app/store/core.py`):
   strict vs widened vs across-close — is any consumer keyed wrong (both stores)? Is the
   hold-vs-resurrect asymmetry sound? Is the P-B full sell-side quarantine the right posture, and
   is PD-1 (`../CAMPAIGN-0002-claude/BLOCKED-DECISIONS.md`) the right shape for its release valve?
3. **Session-close truth:** P-A sweep atomicity/ordering/dedupe across stores; the spared counter;
   replay determinism (a dedicated cross-store stream pin exists — try to falsify it).
4. **Option B flatten** (REV-0024's original scope): TOCTOU closure under one lock hold; retry
   convergence (`OPEN_BUY_STATUSES` == cancel set); override survival; the documented exclusion
   of `SUBMITTING`/`TIMEOUT_QUARANTINE` from the detected set (ADR-010 §4 wording — acceptable?).
5. **Oracle-edit legitimacy:** P1's reseed of `tests/r2_conformance_oracle.py` was setup-only
   (10 additions, 0 deletions; dual-baseline proof in the plan log). Verify no assertion changed
   and no behavior was smuggled. The two P2 properties made the remaining 4 reds green via CODE.
6. **Docs-vs-code:** the ADR-010 2026-07-17 amendments + INV-090/081/037/052 — already
   conformance-checked in-process (verdict FIX-WORDING, all four fixes applied); re-falsify.
7. **The named P4 finding:** perf gates fail two wall-clock ratios marginally (runtime p95
   3.35–3.77× vs 3×; startup elapsed 12.87–13.15× vs 12×) with ALL structural criteria green —
   baseline-proven pre-existing (parent `15c2dd6`: 3.783× / 15.42×). Weigh: block, accept-with-
   perf-WO, or re-budget.

## In-process review record (context, not a substitute for you)

Six independent lenses ran during the build, all documented in the plan §6 / session log:
Option B (concurrency SHIP, behavior SHIP, test-integrity TESTS-SOUND + 2 defects found→fixed/
parked), P2 (event-log-truth SHIP + 1 HEAD-red found→fixed + 2 advisories→applied; projection-
consumer SHIP + 4 observations OBS-1..4 recorded), P5 (docs-conformance FIX-WORDING → applied).
P3c: independent 23-test coverage mapping (20 covered, 3 pins ported).

## Deliverable

`work/review/REV-0029/result.md`: verdict (`ACCEPT` / `ACCEPT-WITH-CHANGES` / `BLOCK`) +
severity-ranked findings (concrete failing scenario or explicit closure argument each). The
author then applies/disputes per Fable discipline in `disposition.md` + a ledger row; the
review gate for the merge clears on ACCEPT[-WITH-CHANGES] + closed disposition loop.
