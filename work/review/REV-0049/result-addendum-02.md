# REV-0049 independent review result addendum 02

Reviewed target: `4e935851edd26f9f38ea93a9544815f5b49ecf88`

This was a local, offline, deterministic Python independent critical review. Evidence labels below
distinguish `reproduced-live`, `failure-capability`, and `static-trace` evidence. Author checkpoints
and prior green claims were treated only as attack leads.

## Pre-registered local invariant checks

These focused counterexamples were registered from AGENTS.md/CLAUDE.md, ADR-020 through ADR-022,
M1 roadmap item 3, and WO-0147 through `Stop conditions` before reading the re-gate-6 checkpoint:

| ID | Local invariant check | Focused counterexample registered before implementation evidence |
|---|---|---|
| LI-01 | Caller-shaped completion metadata has no public or private M1 authority. | Submit both external proof kinds through the public wrapper and private reducer, then retry a SELL while the unresolved BUY remains open. |
| LI-02 | A residual-stale manual SELL has a bounded retry lifecycle. | Change canonical residual after manual SELL creation; require refusal without debit, exact local retirement, fresh replacement identity, one claim, inert replay, and conflict on a second claim. |
| LI-03 | Query phase is fail-closed without weakening permanent identity order. | Drift a previously applied query to `BOOTSTRAPPING`; require exact replay/conflict before phase policy, while a fresh query refuses without mutation. |
| LI-04 | Raw external closure values cannot become certified through reconstruction or replay. | Forge a matching closed effect/input ledger; separately replay a test-modeled canonical close after certification ends and try the same raw close on a distinct book. |
| LI-05 | Audit reconstruction cannot erase a blocking checkpoint by coordinated omission. | Omit the unresolved claimed BUY and every correlated effect, claim, owner, attempt, closure, binding, input, coverage, reconciliation, and registry field together. |
| LI-06 | Every top-level authority field is exact-shape validated before replay or policy. | Use raw phase/fence strings and integer-false kill state on query/manual paths, including an exact previously applied query replay. |

The production-saboteur lens attacked release, retry, partial mutation, and replay ordering. The
context-free-maintainer lens traced the complete changed choke points and reconstruction projection.
The safety/data-integrity lens re-derived whether any case could create final-claim authority.

## Frozen-object and scope proof

- `git cat-file -t 4e935851...` returned `commit`.
- `41c7e956d1c49b450615a03374bd0ef7ee730357` is an ancestor. The exact successor chain is
  `41c7e956... -> 87dc9f9bd2e21e091dc527355f3fa89f5044f2a0 -> 4e935851...`; the target's direct parent is
  `87dc9f9...`.
- Current `HEAD=e3936f07dbab9df534e75312062d8f3d1382e363` is the target's request-only child. Its only
  target-to-HEAD path is `work/review/REV-0049/request-addendum-02.md`.
- The focused delta contains exactly the six permitted paths: `authority.py`, `venue.py`, their two
  focused test files, WO-0147, and preserved `request-addendum-01.md`. No ADR, reset-queue, runtime,
  store/database, adapter, API/UI, or CI path changed.
- All four reviewed source/test blobs were byte-identical to the target before probes and after
  restoration. Existing untracked coverage/JUnit evidence artifacts were present before review and
  were left untouched.

## Required issue closure

### 1. Original P0 — caller-shaped completion metadata

**CLOSED — reproduced-live + static-trace.**

The public reducer refuses `CloseAcceptanceSet` as an internal authority-changing capability at
`app/execution_core/venue.py:8759-8781`; the package and venue export lists omit the proof/close
representations at `app/execution_core/__init__.py:81-98`,
`app/execution_core/__init__.py:125-230`, and `app/execution_core/venue.py:9047-9070`. Direct private
closure is default-denied at `app/execution_core/venue.py:7274-7282` and the close transition cannot
reach mutation without certification at `app/execution_core/venue.py:7285-7312`. Final effect claim
still rechecks the venue view before mutation at `app/execution_core/authority.py:928-953`.

Fresh outcome: for both `CONTRACT_COMPLETE_RESPONSE` and `COVERED_RECONCILIATION`, the public path
raised `TypeError`, the strongest private path returned `REFUSED`, the book was unchanged, the view
retained one blocking BUY, and a fresh SELL remained `REFUSED / VENUE_UNCERTAIN` with no authority
state change.

### 2. Original P1 — late manual SELL residual retry

**CLOSED — reproduced-live + static-trace.**

The final claim re-reads residual and refuses stale quantity at
`app/execution_core/authority.py:919-927`. `AdvanceManualFlatten` recognizes only the exact
`SELL_CREATED`, residual-stale, correctly bound request, rechecks all sibling/account venue
uncertainty, and returns the same workflow to `READY` at
`app/execution_core/authority.py:1144-1226`. The venue helper retires only a `REQUESTED`, unclaimed,
ownerless, reconciliation-clean `OPEN` target and closes it as reducer-derived `NEVER_DISPATCHED` at
`app/execution_core/venue.py:8812-8869`.

Fresh outcome: a late canonical SELL fill reduced residual by one. The stale claim returned
`REFUSED / RESIDUAL_EXCEEDED`; budget and claim indexes were unchanged. Retry returned `APPLIED`,
retired the stale effect as `CANCELED_BEFORE_DISPATCH + CLOSED`, minted no claim, and debited no
budget. Reusing the stale create input returned `EXACT_REPLAY` without resurrection. A fresh-identity
replacement created and claimed once, debited exactly one unit, exact claim replay was inert, and a
second claim identity returned `CONFLICT` without another debit.

### 3. Original P1 — query phase and permanent ordering

**CLOSED — reproduced-live + static-trace.**

The global authority input replay/conflict lookup remains at
`app/execution_core/authority.py:626-634`. For a new input, permanent query identity is checked before
the exact `RECONCILING | SERVING` phase allowlist at `app/execution_core/authority.py:996-1012`; the
successful debit/index mutation is later at `app/execution_core/authority.py:1031-1046`.

Fresh outcome: after a valid query applied, changing the correctly typed state to `BOOTSTRAPPING`
left exact replay as `EXACT_REPLAY` and a changed input reusing the permanent query ID as `CONFLICT`.
A fresh query returned `REFUSED / PHASE_BLOCKED`. All three retained the predecessor budget, venue,
input/query indexes, and emitted no fresh claim.

### 4. Later P0 — private closure, reconstruction, and replay certification

**CLOSED — reproduced-live + static-trace.**

Hydration validates every retained external proof through the default-deny certification predicate
at `app/execution_core/venue.py:2197-2214`. Fresh private closure remains denied at
`app/execution_core/venue.py:7274-7312`. Canonical input replay/conflict is resolved without a fresh
authority evaluation at `app/execution_core/venue.py:8570-8588`, before the fresh close branch at
`app/execution_core/venue.py:8731-8737`.

Fresh outcome: a forged externally closed effect plus matching close-input ledger raised
`ValueError: external acceptance closure requires M2 adapter-certified coverage`. A close first
applied only inside the scoped test-only certification context returned `EXACT_REPLAY` after that
context ended; changed content under the same input ID returned `CONFLICT`. Both were state-inert.
Submitting the same raw close to a distinct unresolved book returned `REFUSED` and left it unchanged.

### 5. Re-gate-6 P0 — coordinated audit-checkpoint omission

**CLOSED — reproduced-live + failure-capability + static-trace.**

The slow-path checkpoint projection enumerates scope, both registry fields, and every effect, claim,
owner, attempt, closure head/history, execution binding, input, coverage, reconciliation, and
execution-reconciliation tuple at `app/execution_core/venue.py:5781-5800`. Hydration obtains and
exact-types those inputs at `app/execution_core/venue.py:5803-5873`, rebuilds and fully validates the
candidate, then rejects any semantic difference from the supplied opaque checkpoint at
`app/execution_core/venue.py:6660-6665`.

Fresh outcome: the coordinated all-empty replacement raised
`ValueError: M1 audit hydration requires an exact reconstruction of the supplied opaque checkpoint`.
The original book retained one blocking BUY, and control SELLs before and after the attempt both
returned `REFUSED / VENUE_UNCERTAIN` with the original authority state unchanged.

### 6. Re-gate-6 malformed-state acceptance

**CLOSED — reproduced-live + failure-capability + static-trace.**

The constant-work validator checks the exact state, all five top-level object/enum fields, exact
Boolean kill state, optional session, non-negative exact integer budget members, all seven retained
indexes, and the optional grant at `app/execution_core/authority.py:437-473`. Every internally built
state passes the same validator at `app/execution_core/authority.py:485-489`. Reducer entry invokes it
before execution/item validation, replay lookup, policy, or mutation at
`app/execution_core/authority.py:1271-1285`.

Fresh outcome: raw phase and fence strings plus `kill_engaged=0` each raised a field-specific
`TypeError` on both query and manual-control paths. Budget, venue, input, query, manual, and effect
claim indexes remained identical. A previously applied query replayed from a raw-string phase state
raised `TypeError` before returning replay. The mandatory focused parametrization also exercised all
15 top-level fields and passed all 18 cases.

## New findings

No new P0 or P1 was reproduced or established by code-anchored proof. The independent disproof pass
also found no regression in kill, fence, mode, session, budget, binding, residual, venue uncertainty,
parent closure, identity, or bounded-index ordering caused by the focused repair.

## Failure-capability checks and exact restoration

| Reversible mutant | Decisive result | Restored SHA-256 |
|---|---|---|
| Neutralized the exact checkpoint comparison at `venue.py:6660`. | `test_audit_hydration_rejects_coordinated_checkpoint_omission` failed with `DID NOT RAISE ValueError`. | `venue.py`: `32d7d56a218a5ae35eefbe484723548778bb2fb9ef497a7bb4a3ec9ed560b276` |
| Weakened exact Boolean validation from `type(value) is bool` to equality membership at `authority.py:461`. | `test_manual_flatten_rejects_integer_kill_state_before_mutation` failed with `DID NOT RAISE TypeError`. | `authority.py`: `2ff53c9d790615c3594d13e3c08710c15d31c5ebebf661faf8e8bb50f13b8a6e` |

Baseline and final hashes were identical for every mutation-relevant file:

- `app/execution_core/authority.py` — `2ff53c9d790615c3594d13e3c08710c15d31c5ebebf661faf8e8bb50f13b8a6e`
- `app/execution_core/venue.py` — `32d7d56a218a5ae35eefbe484723548778bb2fb9ef497a7bb4a3ec9ed560b276`
- `tests/execution_core/test_authority.py` — `3bb281e30e9014926c7a2e2f1ef442cc3240cd47e80cf88d5180092ed0d6b79d`
- `tests/execution_core/test_venue_provenance_hardening.py` — `0ebbe68d354d95ac8a0b3c619b5321963ebf2fd9767d8a633fdc56426bba19eb`

Both failure-capability checks were performed sequentially and restored in `finally` before any
later gate or this result was written. Final target-to-worktree diff for all four files was empty.

## Fresh reproduction gates

All Python probes used `BROKER_ADAPTER=mock`, `-B`/`PYTHONDONTWRITEBYTECODE=1`, and no pytest cache.

| Gate | Fresh result |
|---|---|
| Four mandatory focused node IDs | PASS — 18/18 parametrized cases |
| `tests/execution_core --maxfail=1` | PASS — 710/710; independent collection also returned exactly 710 node IDs |
| Ruff check with cache disabled | PASS — `All checks passed!` |
| Ruff format check | PASS — 20 files already formatted |
| Mypy with `--no-incremental` | PASS — 8 source files |
| Import-linter with `--no-cache` | PASS — 6 kept, 0 broken |
| Focused range `git diff --check` | PASS |
| Five novel pure scenarios above | PASS — every refusal/replay/conflict was state-compared |

The first format attempt used an invalid Ruff cache environment spelling (`1` instead of a Boolean)
and exited before checking; it was rerun with `true`. A first attempt to map mypy cache to the
Windows `NUL` device produced a mypy internal invocation error before analysis; the successful
cache-disabled rerun used `--no-incremental`. Neither invocation changed a reviewed file.

## Not verified and remaining boundary

- R2, the full repository suite/coverage, SQL/SQLite, broker/adapter behavior, external CI, and
  Python 3.11/3.12 exact-head CI were not run or claimed in this review.
- No credential, network, database, broker, runtime wiring, push, PR, merge, deletion, or cleanup
  action was performed.
- Loading a distinct authenticated persisted checkpoint remains deferred to M2. This review proves
  only exact M1 reconstruction of the supplied opaque checkpoint.
- Clearing this independent gate does not disposition or close WO-0147. Fable/ledger/PKL closeout,
  one final immutable push, and unchanged exact-head Python 3.11/3.12 CI remain required before
  WO-0148 may activate.

## Verdict

ACCEPT
