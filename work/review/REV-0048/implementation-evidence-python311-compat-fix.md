# WO-0146 Python 3.11 compatibility repair evidence

## Frozen object

- Failed closeout candidate: `4b9b47de1936a179478f1c638c4872a4b0935719`
- Failed external run: GitHub Actions `30746436486` (#682)
- Python 3.11 job: `91492722592` — failure in full coverage step
- Python 3.12 job: `91492722638` — success
- Docs-only bounded re-gate: `a7dbc0390a0cf3f06c0769b29389de34ea2fed10`
- Repair freeze: `ba70c46b05f3ec3d653159f00193c03711ba82e7`

The repair freeze changes no production file. Relative to the re-gate it changes only
`tests/execution_core/test_fill_position_stateful.py` and the WO FIX record. WO-0147 remains
inactive.

## RED and root cause

At exact `4b9b47de`, Python 3.11 passed every gate before the full suite, then reported three
`RecursionError` failures:

- `test_property_duplicate_does_not_count_clamp_reject_or_clear_integrity`
- `test_property_revision_induced_negative_is_exact_and_permanently_quarantined`
- `test_property_fast_non_tail_revision_never_invokes_or_exposes_slow_candidate`

All three traces enter `_apply()` at test line 234 while evaluating `repr(root_heads)` before the
reducer call. The auto-generated representation recursively descends through the immutable radix
tree. This is a Python 3.11 test-harness compatibility defect, not an observed reducer defect.

## Correction and failure capability

The helper now snapshots public constant-work component commitments plus bounded binding and fact
representations. It still calls the reducer twice, compares the transitions, and compares every
input snapshot before/after.

Three transient hostile wrappers mutated state after the second deterministic reducer call. All
were killed by the restored guard:

```text
KILLED position-component
KILLED root-binding
KILLED fact-payload
```

The final test file is 34,166 bytes, SHA-256
`caa2232eb1500dc499b2f2566ae2d030f4891f38520930921fa00740f872b6f3`.

## Fresh gates

- Three exact failed nodes: pass.
- Same nodes with local Python 3.12 recursion limit reduced to 700: pass.
- Complete stateful file: 7/7 pass.
- Complete `tests/execution_core`: 521/521 pass.
- Ruff check and format-check: pass.
- mypy over seven execution-core source files: pass.
- Import Linter: 6 contracts kept, 0 broken.
- AI-OS install, version, ledger, PKL, and disposition checks: pass.
- R2 conformance: 61/61 pass under `BROKER_ADAPTER=mock` with a fresh disposable
  workspace-local test directory.
- Full repository collection: 5,109 cases in 214 files.
- Full repository coverage run: exit 0 in 1,057.3 seconds under `BROKER_ADAPTER=mock` with a fresh
  disposable workspace-local test directory.
- Scope and diff checks: pass; no production path changed.

The first R2 attempt reached no test body because Windows denied pytest's default temp root. The
recorded result above is the fresh rerun with an explicit workspace-local `--basetemp`; it is an
environment recovery, not a product retry.

## Coverage identity

The fresh full run reports:

```text
covered lines:     17,537 / 18,503
covered branches:   6,080 / 6,890
combined exact:     93.00594652069468%
```

- Binary: 1,765,376 bytes, SHA-256
  `7cd7642ff617c37405f208ed8ab037240391bbf58c34bb34e3590c0a5308c02a`
- JSON: 1,739,722 bytes, SHA-256
  `68ccc2249c71ef492f0f2b142bbbaff3fdb6898861396c3c4943ecfc293a6392`

The coverage artifacts are untracked evidence and are preserved. No cleanup occurred.

## Exclusions and remaining gate

No broker credential, Alpaca/Paper activity, live endpoint, persistent application database,
runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup was used. The existing
R2/full fixtures used only the separately authorized disposable test SQLite path with
`BROKER_ADAPTER=mock`. The prohibited R1 DDL result was not relied upon.

Independent exact-diff review and an immutable successor passing unchanged exact-head Python 3.11
and 3.12 CI remain required. This file is implementation-seat evidence, not reviewer acceptance.
