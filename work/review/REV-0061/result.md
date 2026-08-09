# Independent WO-0152 coverage-ratchet semantics review

Review target: `codex/arch-reset-2026-07-r1` at base/HEAD
`ae626f56fb05c09b312a7383326ebbf9ba584cd3`, candidate manifest SHA-256
`a91a8f03327b07f5448c60549493dc5b777c10a22fe126da9710b085f6c4a7c2`.
All eight manifest rows and retained `coverage-e3.json` matched their pinned
SHA-256 values before and after focused verification.

## Findings

### [P1] The new CI coverage gate can be removed without any test failing

- Location: `.github/workflows/ci.yml:98`; `pyproject.toml:41`;
  `tests/test_ci_lock_liveness_pins.py:24`; `tests/test_coverage_ratchet.py:1`
- Requirement: The amendment requires both coverage dimensions to remain
  mandatory in CI, and the repository review rule requires a material behavior
  change to have a failure-capable test.
- Evidence: `[static-reasoning]` The workflow currently generates branch-aware
  JSON and invokes the validator in the immediately following step, so the live
  ordering is correct. However, `tests/test_coverage_ratchet.py` never reads the
  workflow or configuration. The existing CI lock test asserts only the old
  pytest-command substring, which still matches the new command. Deleting the
  validator step therefore leaves `fail_under = 0` and no coverage floor while
  every current gate test can remain green.
- Impact: A later workflow edit can silently remove both mandatory ratchets,
  converting full-suite CI into a coverage-report-only step without a failing
  local or CI lock control.
- Resolution: Add a failure-capable integration pin in an authorized test path
  that requires branch-aware JSON generation followed by the exact validator
  command, preserves `source = app` and branch instrumentation, and proves that
  removal or reordering of the validator is rejected.

### [P1] Required fail-closed input rules are not isolated by the tests

- Location: `.ai-os/scripts/check_coverage_ratchet.py:37`;
  `tests/test_coverage_ratchet.py:99`
- Requirement: The amendment requires rejection of missing, malformed,
  negative, internally impossible, and non-branch coverage data; those controls
  must be failure-capable rather than satisfied by an unrelated error.
- Evidence: `[static-reasoning]` The validator implementation presently rejects
  the named cases, but the tests contain no negative numerator/denominator
  specimen and no otherwise-valid report with `branch_coverage` false. The
  truthy-boolean specimen also omits branch metadata, so changing exact-integer
  validation to accept `bool` still leaves an unrelated branch-instrumentation
  problem and satisfies the broad `assert ...problems`. Invalid JSON/file-read
  refusal in the CLI is likewise not exercised. These mutations can survive the
  current suite despite removing named fail-closed behavior.
- Impact: The candidate does not provide the failure-capable evidence required
  for its own malformed-input contract; independent gate guards can regress
  while the six focused tests remain green.
- Resolution: Add isolated valid-context specimens for negative values,
  non-branch metadata, and exact-integer type rejection, asserting their exact
  failure reasons; add malformed/unreadable CLI input controls and pin the exact
  `93.00` / `85.25` constants or just-below boundaries.

### [P2] The pytest configuration still describes a disabled built-in floor

- Location: `pyproject.toml:9`
- Requirement: Gate instructions must identify the actual owning check so local
  evidence cannot be misreported.
- Evidence: `[static-reasoning]` The introductory comment says the “floor below
  then applies,” but the value below is now `fail_under = 0`; the mandatory
  floors are owned by the separate JSON validator.
- Impact: A local operator can reasonably treat the coverage-enabled pytest
  command as self-gating and report a false green without running the validator.
- Resolution: Update the comment to name the JSON report plus validator as the
  complete local/CI gate sequence.

## Reproduced evidence and adjudication

- `[reproduced-live]` Retained arithmetic independently resolves to
  `24819 / 26530 = 93.550697323784395...%` executable-line coverage,
  `8457 / 9920 = 85.252016129032258...%` branch coverage, and
  `33276 / 36450 = 91.292181069958847...%` coverage.py combined coverage.
- `[static-reasoning]` Separate `93.00%` line and `85.25%` branch floors are a
  defensible root correction rather than a concealed waiver: line coverage does
  not fall below the configured 93 floor, branch coverage gains an explicit
  observed-baseline floor, neither dimension can conceal the other, branch
  instrumentation and `source = app` remain unchanged, prior combined failures
  remain negative evidence, and exact-head Python 3.11/3.12 success is still
  required before closeout.
- `[reproduced-live]` Six focused ratchet tests passed; the retained JSON passed
  the CLI with both exact conclusions; two focused E3 inventory/source-policy
  controls passed; Ruff check, Ruff format check, Mypy for the validator, and
  candidate diff checking passed.
- `[static-reasoning]` The candidate changes no `app/**` path, coverage omit or
  pragma, runtime, persistence, database, broker/network, credential, or M2
  surface. The large E3 delta remains test-only and within the active
  work-order's behavior/replay/mutation/boundedness scope.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 1
Unverified: the claimed 5,963-test full local run and external exact-head Python 3.11/3.12 CI were not rerun in this bounded seat; `coverage-e3.json` was used only for arithmetic.
