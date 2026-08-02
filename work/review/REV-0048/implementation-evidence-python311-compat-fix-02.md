# WO-0146 complete retained-graph compatibility repair evidence

## Frozen object and recovery chain

- Failed closeout candidate: `4b9b47de1936a179478f1c638c4872a4b0935719`
- Failed external run: GitHub Actions `30746436486` (#682)
- Python 3.11 job `91492722592`: failed while recursively rendering the stateful-test input
- Python 3.12 job `91492722638`: passed
- First repair freeze: `ba70c46b05f3ec3d653159f00193c03711ba82e7`
- Reviewer-owned addendum-03: preserved `BLOCK`
- Incomplete retained-leaf freeze: `1189d88` (independently blocked on two auxiliary maps)
- Docs-only complete-graph re-gate: `fe85336c962e13ba34a57c52856c65bda4fa83a7`
- Final implementation freeze: `5a8984133354ecfa0343d6fb4a7fdaef38d56dab`

The final implementation diff `fe85336..5a89841` changes only
`tests/execution_core/test_fill_position_stateful.py` and the WO FIX record. The cumulative
`4b9b47d..5a89841` recovery delta contains exactly five allowed paths: that test, the WO, and the
three preserved addendum-03 evidence/request/result artifacts. `app/execution_core` remains
byte-identical at tree `09f93d1577dd2c0e1499acf56cf4688cac8be665`; the complete `app` tree remains
`b144102e4c99c9e889cd7e22591c884630187188`. WO-0147 is absent and inactive.

## RED, root cause, and correction

Two permanent parameters were added before the complete graph projector changed. The exact focused
run returned two expected failures:

```text
root-head:          passed
seen-fact:          passed
broker-scope-count: FAILED -- expected immutable-input assertion did not occur
prefix-commitment:  FAILED -- expected immutable-input assertion did not occur
```

The `1189d88` helper materialized primary entries but still trusted cached commitments for
`RootHeadIndex._broker_scope_counts` and `SeenFactIndex._prefix_commitments`. Hostile retained-leaf
mutation changed the public `broker_root_count()`/`has_prefix()` answers without changing the cached
commitment or the incomplete fingerprint.

At `5a89841`, the test-only oracle uses an explicit work stack to project the complete input and
output dataclass/tuple graphs. It records exact types, every field, every radix node and edge,
retained values, cached commitments, and reference ordinals. The ordinal scheme preserves alias
topology and terminates on hostile cycles without embedding unstable object IDs. No persistent
container is recursively rendered. The same complete projection is authoritative for output
determinism; ordinary index equality remains a secondary assertion.

Static production call-site review found no use of `RootHeadIndex` or `SeenFactIndex` equality.
Production binding, recovery, and venue paths use commitments, counts, bindings, and alias checks,
and public constructors derive the auxiliary maps. The omitted equality fields were therefore a
test-oracle limitation under hostile private mutation, closed by the complete projection without a
production semantic change.

## Permanent failure-capable controls

Fifteen named cases pass:

- five immutable-input mutations: retained root head, retained seen fact, broker-scope count,
  prefix commitment, and current fact;
- two second-output divergences: broker-scope count and prefix commitment;
- two position sequence leaves: root key and effective head ID;
- five hidden-structure mutations: observed-root occupancy, cached radix value commitment,
  required shared-sequence alias, required binding alias, and a self-referential radix cycle; and
- one overfill-scope occupancy mutation that changes the public query.

A separate read-only hostile pass attacked all six direct maps, all three sequence backing maps,
all three sequence lengths/leaves, retained nested values, cached node metadata, aliases, cycles,
sibling ordering, current fact, bindings, and second-output divergence. Every mutation was killed.
Two independently built equivalent graphs projected identically, and the runtime leaf inventory
contained only immutable scalar, enum/flag, decimal, and fraction values. This pass returned
`ACCEPT`; it is supporting evidence, not the reviewer-owned result.

## Fresh gates at the final implementation freeze

- Fifteen named mutation/structure controls: pass.
- Complete stateful file at recursion limit 700: 22/22 pass.
- Complete `tests/execution_core`: 536/536 pass.
- Ruff check and format-check over `app/execution_core` and `tests/execution_core`: pass.
- mypy over seven execution-core source files: pass.
- Import Linter: 6 contracts kept, 0 broken.
- AI-OS install/version/ledger/PKL/disposition checks: pass.
- Exact WO scope and `git diff --check`: pass.
- R2 conformance: 61/61 pass with `BROKER_ADAPTER=mock` and a fresh disposable test directory.
- Full repository collection: 5,124 cases.
- Full repository coverage: 5,112 passed, 11 skipped, 1 expected xfail; exit 0 in 1,358.8
  seconds with `BROKER_ADAPTER=mock` and a fresh disposable test directory.

The preceding `_3` full-run attempt was stopped by the command tool's 1,204-second ceiling at 28%,
not by pytest. Its partial disposable test directory is preserved and is inadmissible. It emitted no
coverage artifact. The recorded full result above is the fresh `_4` run with a longer ceiling.

## Exact coverage identity

```text
covered lines:       17,537 / 18,503
covered branches:     6,080 / 6,890
combined numerator:  23,617
combined denominator:25,393
combined exact:       93.00594652069468%
```

- Binary `.coverage_wo0146_py311_fix_full_4`: 1,765,376 bytes, SHA-256
  `7cd7642ff617c37405f208ed8ab037240391bbf58c34bb34e3590c0a5308c02a`
- JSON `.coverage_wo0146_py311_fix_full_4.json`: 1,739,722 bytes, SHA-256
  `768c86f13505eb2fb606fc1542420ba1ed9cf0504c8b1835b3b94951a68964ec`
- Final stateful test: 46,443 bytes, SHA-256
  `c3d0a4111eb53bf4fb242e80391148eb34d383b4f6bd2c87d8066bf2bf1c1551`

All coverage artifacts and disposable workspaces remain untracked and preserved. No cleanup or
deletion occurred.

## Exclusions and remaining gate

No credential, Alpaca/Paper activity, live endpoint, persistent application-database mutation,
runtime wiring, PR/merge, branch/worktree retirement, deletion, or cleanup was used. Existing R2
and repository fixtures used only the separately authorized disposable test-only SQLite path under
the forced mock broker. The prohibited R1 DDL result was not used.

A reviewer-owned successor addendum and one immutable successor passing unchanged exact-head Python
3.11 and Python 3.12 CI remain mandatory. This is implementation-seat evidence, not acceptance.
