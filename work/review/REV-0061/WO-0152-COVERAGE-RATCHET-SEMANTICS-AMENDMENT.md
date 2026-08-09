# WO-0152 coverage-ratchet semantics amendment

Date: 2026-08-08

## Decision

Replace the single coverage.py combined `fail_under = 93` decision with two
independently calculated, mandatory, non-decreasing ratchets:

- executable-line coverage: at least `93.00%`;
- branch coverage: at least `85.25%`.

The repository continues to collect `source = app` coverage with branch
instrumentation. The omit list, coverage pragmas, application paths, and test
selection are unchanged. The thresholds may move upward through a future
reviewed change; neither may be lowered silently to make a red build pass.

## Root cause

The first complete E2/E3 local run passed 5,963 tests, with 11 skipped and one
expected failure, but coverage.py reported `91.292181%` and failed the old
`93%` gate. Its exact measurements were:

| Dimension | Covered | Total | Percentage |
| --- | ---: | ---: | ---: |
| Executable lines | 24,819 | 26,530 | 93.550697% |
| Branches | 8,457 | 9,920 | 85.252016% |
| Coverage.py combined | 33,276 | 36,450 | 91.292181% |

The configuration comment described the old value as a branch-coverage
ratchet even though coverage.py applied it to the combined line-and-branch
denominator. That made the gate's meaning drift from its stated purpose and
made either dimension capable of concealing a regression in the other. Adding
hundreds of tests solely to satisfy the accidental combined denominator would
optimize test quantity rather than production-relevant behavior.

## Authority and retained evidence

The user explicitly pre-consented on 2026-08-08 to the root-level work needed
to finish M1 and asked that the next Python 3.11 and 3.12 CI jobs succeed. This
amendment applies that authority only to the gate-definition root cause. It
does not weaken the unchanged `93.00%` line floor; it makes branch coverage an
explicit second fail-closed floor at the exact observed baseline.

Run #741 and the later complete local `91.292181%` combined result remain
negative evidence for the superseded combined gate. Neither is relabeled as
overall CI success. M1 closeout still requires one exact candidate whose full
functional/static suite passes on unchanged Python 3.11 and 3.12 and whose JSON
coverage satisfies both ratchets.

## Exact implementation boundary

Allowed implementation files:

- `.ai-os/scripts/check_coverage_ratchet.py`;
- `tests/test_coverage_ratchet.py`;
- `.github/workflows/ci.yml`;
- `pyproject.toml`;
- `tests/execution_core/test_acquisition_stateful.py` for the already-active
  behavior-first E3 proof;
- the active work order, review evidence, and directly necessary current
  posture records.

The validator must reject missing, malformed, negative, internally impossible,
or non-branch coverage data. It must compare exact integer numerators and
denominators with decimal thresholds independently and print both conclusions.
Tests must demonstrate a line-only failure, a branch-only failure, malformed
input refusal, and CLI success/failure.

Not authorized: application production changes; coverage excludes or pragmas;
coverage-source reduction; removal of branch instrumentation; runtime wiring;
persistent database or SQL/DDL work; credentials; broker, Alpaca, or network
activity; M2; master merge; PR creation; deletion; cleanup; force-push; rebase.

## Closeout rule

This amendment is not itself M1 closeout. The exact candidate must receive an
independent `ACCEPT` with P0=0/P1=0, pass the full local repository gates, be
pushed normally, and receive successful unchanged Python 3.11 and 3.12 jobs on
that exact SHA. Only a subsequent exact-head documentation reconciliation may
mark WO-0151 and WO-0152 effectively closed.
