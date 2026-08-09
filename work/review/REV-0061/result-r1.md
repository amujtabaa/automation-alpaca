# Independent WO-0152 coverage-ratchet R1 recheck

Review target: `codex/arch-reset-2026-07-r1` at base/HEAD
`ae626f56fb05c09b312a7383326ebbf9ba584cd3`, replacement manifest SHA-256
`230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309`.
All ten manifest rows and retained `coverage-e3.json` matched their pinned
SHA-256 values before focused verification.

## Findings

None.

## Prior-finding closure and regression checks

- `[reproduced-live]` The prior CI-integration P1 is closed. The focused test at
  `tests/test_coverage_ratchet.py:159` requires exactly one branch-aware JSON
  measurement command, exactly one validator command, measurement before
  enforcement, `source = ["app"]`, `branch = true`, and `fail_under = 0`.
  In-memory removal and reorder mutations were both rejected by those exact
  predicates.
- `[reproduced-live]` The prior fail-closed-controls P1 is closed. Isolated
  otherwise-valid cases now own negative totals, exact-integer rejection, and
  disabled branch instrumentation; CLI controls own invalid JSON and missing
  files. The tests assert the specific refusal reasons, and the exact `93.00`
  line / `85.25` branch constants are pinned.
- `[reproduced-live]` The prior configuration-comment P2 is closed.
  `pyproject.toml:9` now identifies branch-aware JSON generation followed by
  the external validator as the complete local/CI gate.
- `[reproduced-live]` Gate semantics did not regress: the validator, workflow,
  stateful E3 evidence, and accepted amendment hashes are unchanged from the
  first candidate. The independent floors remain `93.00%` lines and `85.25%`
  branches; `source = ["app"]`, branch instrumentation, exclusions, and the
  authorized test-only E3 scope are unchanged. No `app/**` path entered the R1
  delta.

## Focused evidence

- `11 passed`: `tests/test_coverage_ratchet.py`.
- Retained `coverage-e3.json` passed the validator with
  `24819 / 26530 = 93.550697%` lines and
  `8457 / 9920 = 85.252016%` branches.
- Ruff check, Ruff format check, Mypy for the validator, and candidate
  `git diff --check` passed.
- All ten manifest rows, the retained coverage evidence, and retained
  predecessor packet hashes were rechecked after verification without drift.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: the full repository suite and external exact-head Python 3.11/3.12
CI were intentionally not rerun in this focused R1 seat.
