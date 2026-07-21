---
type: Work Order
title: "Signal Seat R3: red-first test-corpus port (branch-staged, never merged red)"
status: CLOSED
work_order_id: WO-0128
wave: signal-seat revival (O-3 path a; ladder step R3)
model_tier: mid
risk: low
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen / implementer: Codex ultra session
created: 2026-07-20
gated_surface: none (staging branch only; nothing lands on master in this WO)
---

# Work Order: port the 12-file signal test corpus onto a staging branch, red

> The archive's most portable asset is its regression corpus (plan §5 tests table: 12 KEEP
> files + helpers + 2 hunk cherry-picks). Porting it red-first BEFORE the implementation WOs
> means R4/R5/R6/R7 each merge a slice green — the revival is test-driven by construction.
> **The staging branch is never merged while red**; each test slice lands only with its green
> implementation WO.

## Goal

A staging branch (`codex/signal-tests-staging`) carrying the rebased signal test corpus,
re-baselined against the WO-0127-amended ADR/spec text, collecting cleanly, red for the right
reason (missing implementation), with a slice map telling each implementation WO which files it
must turn green.

## Context packet

- `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §5 tests table (per-file verdicts + the two
  hunk-only items) + §6 step R3
- Archive test files via `git show 'origin/archive/claude-wo-0001-install-checks-2x5ys8:tests/<name>'`
- `tests/conftest.py` (the `any_store` seam the corpus relies on) + master's
  `tests/test_import_boundaries.py` / `tests/test_phase6_facade_foundations.py` (hunk targets)
- The WO-0127-amended spec text (constants, reason codes, TTL formula) — the re-baselining source

## Allowed paths

```yaml
allowed_paths:
  - tests/signal_seat_helpers.py         # staging branch only
  - tests/test_signal_*.py
  - tests/test_cockpit_operator_header.py
  - tests/test_import_boundaries.py      # 5-line _SANCTIONED_ALPACA_REACHERS hunk ONLY
  - tests/test_phase6_facade_foundations.py   # the two get_actor tests ONLY
  - work/**                              # slice map + close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**            # porting tests, not code
  - docs/**
  - .github/**
```

## Required behavior

- [ ] Rebase the 12 KEEP files + helpers per the plan's per-file notes; cherry-pick ONLY the
      two named hunks (whole-file ports of the hunk targets are forbidden — master drifted).
- [ ] Re-baseline constants/citations against the WO-0127-amended text (TTL bounds, reason
      codes, transport vocabulary, D-SIG-7/8 outcomes); convert archive REV citations to
      archive-ref provenance.
- [ ] Every file COLLECTS on the branch; failures are ImportError/assertion-red for missing
      implementation, never syntax/fixture rot. Never weaken a ported test to fit future code.
- [ ] Produce the slice map: test file → owning implementation WO (R4 store / R5 endpoint /
      R6 rails / R7 conversion) → committed to `work/` on the branch.

## Fable v3 evidence

### GATE — VERIFIED

- Re-read the kickoff, this branch's ULTRA state, this WO, the reconciliation-plan test table,
  root `conftest.py`'s `any_store` seam, both hunk targets, and the stabilized WO-0127 history
  before porting.
- Archive source was read directly from
  `origin/archive/claude-wo-0001-install-checks-2x5ys8`; only the 12 listed assets and the two
  explicitly named hunk targets were ported.

### RED — VERIFIED / INTENTIONAL

- OS-temp `pytest --collect-only` produced 51 collected existing/seam-compatible tests, then ten
  ImportErrors for absent planned implementation symbols: signal rails/facade, signal projectors
  and constants, launcher/launch guard, and signal models. No syntax error or fixture failure was
  observed. This is the expected R4/R5 red boundary, not a green claim.

### FIX — NOT APPLICABLE

- Root cause of red is intentionally missing future implementation. This WO forbids `app/**` and
  must not add shims, weaken assertions, or make red tests green. The slice map assigns every
  asset to R4, R5, or R6 for a future green merge.

### DONE — VERIFIED

- `work/completed/WO-0128-signal-corpus-slice-map.md` records the file-to-owner map and exact red
  reasons. The staging branch is never merged while red and must remain red in CI until slices
  ship with their implementation WOs.

## Acceptance criteria

- [x] Branch intentionally not pushed per the current operator instruction; collection output is
      pasted above and red reasons are audited by implementation seam. If pushed later, CI is
      expected to be RED and that is not a merge candidate.
- [x] Slice map complete; master untouched; Fable DONE with evidence.

## Stop conditions

Stop if a ported test's contract contradicts the amended ADR text — that is WO-0127 feedback,
not a test edit. Runs after WO-0127's text stabilizes; no other dependency.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
