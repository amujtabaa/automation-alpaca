# WO-0168c checkpoint bundle — HUMAN-GATE (schema/DDL)

Status: **HUMAN-GATE — no schema, database, broker, credential, or network action performed**

Date: 2026-08-24

```text
Work order:      WO-0168c (frozen non-serving checkpoint, contract R20)
Branch:          codex/claude-opus-m2-wo0168c-r1
                 (mirrored to claude/m2-execution-continuation-vz91tk at the same commit)
Base commit:     344c32b  feat(checkpoint): R20 s4 venue HumanCoverages
Candidate head:  faa964e2eaf3592c70ccff21c851e8adb85c3402
Candidate tree:  9843d382a6c8121350ba4afae398149ec8ce70af
Changed paths:   app/execution_core/persistence/checkpoint_codec.py
                 tests/execution_core/test_persistence_runtime_checkpoint_pure.py
```

## Commits created

```text
d22bf0e feat(checkpoint): R20 s4 venue ClosureHeads
ab67de4 feat(checkpoint): R20 s4 venue Reconciliations
0d16933 feat(checkpoint): R20 s4 venue BootstrapTargets
8e81cbe feat(checkpoint): R20 s4 venue ExecutionReconciliations
1597152 feat(checkpoint): R20 s2 authority AcquisitionDescriptors and AcquisitionSlots
720d390 feat(checkpoint): project the authority emergency grant row
faa964e test: prove the projected venue and authority wires pass their own validators
```

## Scope completed

R20 section 4 and section 2 projection are complete. The projector now carries **no
whole-family refusal at all**: all fifteen venue families and all authority collections
project from proof-selected direct keys.

Families added this checkpoint: `ClosureHeads`, `Reconciliations`, `ExecutionReconciliations`,
`BootstrapTargets` (venue); `AcquisitionDescriptors`, `AcquisitionSlots`, and the
`EmergencyGrant` member (authority).

Nested forms newly built for the bootstrap row: venue scope, execution binding, the 6-member
inert transition cursor, the 10-member symbol authority summary, and the 25-member inert
transition proof.

## RED evidence

Strict RED-first was **not** followed uniformly: for most families the encoder and its tests
were written together and run as one step. What was verified instead is that the new refusal
controls can fail, by mutation:

```text
MUTANT [drop reconciliation unreferenced-input cardinality] -> 1 test(s) failed
MUTANT [compare all three acquisition scope maps to the slot count] -> 1 test(s) failed
MUTANT [sort reconciliation inputs by Python string order] -> 1 test(s) failed
```

The third mutant matters most: it proves contract section 2.4 canonical ordering is pinned by
a test rather than merely intended, since Python string order and proof order disagree on the
fixture's inputs.

## GREEN / focused evidence

```text
$ .venv/bin/python -m pytest tests/execution_core/test_persistence_runtime_checkpoint_pure.py
105 passed in 2.83s

$ .venv/bin/python -m pytest tests/test_import_boundaries.py -q
......                                                                   [100%]
```

## Full / static / governance evidence

```text
$ .venv/bin/python -m ruff check app/ tests/
All checks passed!

$ .venv/bin/python -m mypy app/
Success: no issues found in 95 source files

$ .venv/bin/lint-imports
Contracts: 6 kept, 0 broken.

$ .venv/bin/python -m ruff format --check app/ tests/
8 files would be reformatted, 329 files already formatted
```

The 8 unformatted files are pre-existing and are **not** in this checkpoint's changed paths:
`app/recorder/{__init__,models,store}.py`, `tests/test_signal_ingest_store.py`,
`tests/test_signal_projector_forward_compat.py`, `tests/test_signal_seat_models.py`,
`tests/test_tape_recorder.py`, `tests/test_wo0114_pd1_release_valve.py`.

## Known failures and NOT_RUN items

### 1. HUMAN GATE — the schema DDL cannot install (blocks 55 SQLite tests)

`SCHEMA_DDL` contains two `RAISE (ABORT, ...)` calls whose message is a `||` concatenation.
SQLite's grammar requires that argument to be a **string literal**, not an expression, so
`install_schema` aborts on the first of them and no database can be created at all.

`app/execution_core/persistence/schema.py:1739`

```sql
        'acquisition predecessor must be retired and compatibility-equal '
            || 'at the immediate prior ordinal of the same scope'
```

`app/execution_core/persistence/schema.py:3056`

```sql
        'venue_effect CLOSED requires exact proof; NEVER_DISPATCHED requires '
            || 'CANCELED_BEFORE_DISPATCH and no claim'
```

Independent minimal reproduction (not the production helper):

```text
concatenated:   REFUSED -> near "||": syntax error
single literal: ACCEPTED
sqlite3 library version: 3.45.1
```

Observed failure through the real installer:

```text
app/execution_core/persistence/schema.py:4781: in install_schema
    connection.execute(statement)
E   sqlite3.OperationalError: near "||": syntax error
```

### 2. HUMAN GATE — `_SCHEMA_CATALOG_SHA256` is pinned to an unproducible value

`schema.py:4618` pins `145393452d7bd0f0227076f14daa5b6115e44581609e456646b82de663df0a08`.
Because the DDL has never installed, that pin has never been verified against a real catalog.
Joining the two messages into single literals **without changing one byte of message text**
yields catalog digest `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`.

`schema_ddl_digest()` is derived from the DDL text itself, so it needs no separate update.

### Measured effect of the gated change (measurement only — reverted, nothing committed)

| State | SQLite checkpoint failures |
| --- | --- |
| At candidate head (unchanged) | 55 |
| With the two `||` joins only | 55, all now "installed schema catalog differs from the exact contract" |
| With the joins **and** the re-pinned catalog digest | 48 (7 pass) |

The 48 remaining are **not** schema problems:

- 47 × `ValueError: venue scope has the wrong exact shape` — `_projected_envelope` in
  `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py:56` builds a stub wire
  (`["m2.venue.State/v1", *([None] * 22)]`). Now that projection exists, that fixture must
  project a real venue/authority row. This is ordinary in-scope test work, blocked only
  because it cannot be run until the schema installs.
- 1 × `AssertionError: (3, 'SCAN SELECTED')` in
  `test_all_thirteen_selection_queries_have_bounded_indexed_plans` — a query-plan assertion,
  diagnosed no further.

The gated file was restored and confirmed byte-identical to its pre-measurement copy; the
worktree is clean and no measurement patch is committed.

### 3. Pre-existing RED control, deliberately not "fixed"

`tests/execution_core/test_persistence_write_capability.py::test_setup_issuer_and_support_imports_have_the_frozen_direction`

```text
E   AssertionError: assert {'test_persis...apability.py'} <= {'test_persis...apability.py'}
      Extra items in the left set:
      'test_persistence_runtime_checkpoint_sqlite.py'
```

Entered at commit `7887251` ("test: stage held checkpoint SQLite proof"), before this session.
The drive document proposed fixing it by inlining capability issuance, but that is impossible:
the sibling control `test_setup_issuer_has_one_test_support_route_and_detector_is_failure_capable`
requires `persistence_setup_support.py` to be the only test file naming
`_issue_setup_write_capability` in any spelling. The two controls together admit exactly one
issuer-naming module and exactly five importers of it; the checkpoint SQLite test is a
legitimate sixth consumer.

Adding a filename to the allow-list would make the control pass, and I judge the control's two
real properties (production never imports test support; the test-side route is singular) to be
preserved by it. I did **not** do that. This is a write-capability surface and CLAUDE.md is
explicit — "Never weaken a test to make code pass. Fix the code or flag the conflict." Routing
the import through `conftest.py` would also pass both controls by exploiting the `test_*.py`
glob; that is evasion, not a fix, and was likewise rejected.

**Requested decision:** authorize the enumeration update, or name a different route.

### NOT_RUN / NOT_EVALUATED

- `python tests/r2_conformance_oracle.py` — NOT_RUN this checkpoint.
- `pytest tests/test_wo0113_repair_scaling.py` — NOT_RUN this checkpoint.
- Full `pytest` across the repository — NOT_RUN; only the focused suites above were executed.
- REV-0078 independent review — NOT_RUN (no packet opened).
- The 48 post-gate SQLite failures — NOT_EVALUATED beyond the classification above.
- WO-0168b, WO-0169, WO-0170 — not started.

## Schema, database, broker, credential, or network activity performed

**None.** No `install_schema` against any persistent database, no credentials, no outbound
broker or network call. The measurement described above ran the installer only against
pytest `tmp_path` scratch databases and `:memory:`, and its source patch was reverted.

## Requested next action

1. Authorize the two `RAISE (ABORT, ...)` single-literal joins and the `_SCHEMA_CATALOG_SHA256`
   re-pin (schema/DDL — human-gated). Message text is byte-identical either way.
2. Decide item 3 above (frozen import-direction control).

With (1) approved, the next bounded step is to replace the stub wire in
`_projected_envelope` with a real projection and run only the approved fresh-file SQLite gate.
