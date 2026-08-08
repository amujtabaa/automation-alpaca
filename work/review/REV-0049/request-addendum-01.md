---
type: Review Request Addendum
rev_id: REV-0049
addendum: 01
title: "WO-0147 authority lifecycle and private closure certification repair"
status: AWAITING_REVIEW
failed_targets:
  - 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
  - 98855655a5a51f04b7be95ba65c0c58fbef44b39
blocked_result_commit: 90b5bc4ed2e1ffb2c0056192fd85204d700c4b32
red_targets:
  - 2c29856afec830e41c38224eb0fd6c763ba1ef67
  - 4bf1101d7dd95b5f65742e99999ba624a67f9120
reviewed_target: 41c7e956d1c49b450615a03374bd0ef7ee730357
base: 1d294e0ac29dcd169a4733df3aa9cbd337dc8787
date: 2026-08-02
---

## Independent assignment

Review the final bounded repair at
`41c7e956d1c49b450615a03374bd0ef7ee730357`. The original `REV-0049/result.md` and the later
author-side hostile pre-flight are negative evidence, not authority. Re-derive every conclusion
from accepted ADRs, exact source, and fresh failure-capable probes. Do not edit any request,
implementation, test, work order, or prior review artifact. Deposit findings only as
`work/review/REV-0049/result-addendum-01.md`.

You are the independent review seat. Author-recorded GREEN, mutation, coverage, scope, and hostile
pre-flight claims are attack leads, not proof. Produce findings only and end with exactly one
verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.

## Frozen objects

```text
original failed implementation:  1d294e0ac29dcd169a4733df3aa9cbd337dc8787
preserved BLOCK result commit:   90b5bc4ed2e1ffb2c0056192fd85204d700c4b32
first remediation RED:           2c29856afec830e41c38224eb0fd6c763ba1ef67
hostilely disproved first repair: 98855655a5a51f04b7be95ba65c0c58fbef44b39
private-seam remediation RED:    4bf1101d7dd95b5f65742e99999ba624a67f9120
final repaired target:           41c7e956d1c49b450615a03374bd0ef7ee730357
```

Verify object identity, parentage, and exact path inventory. Inspect both the complete repair and
the private-seam delta:

```powershell
git diff 1d294e0ac29dcd169a4733df3aa9cbd337dc8787..41c7e956d1c49b450615a03374bd0ef7ee730357 -- app/execution_core tests/execution_core work/active/WO-0147-reset-kernel-c-trading-authority-controls.md
git diff 98855655a5a51f04b7be95ba65c0c58fbef44b39..41c7e956d1c49b450615a03374bd0ef7ee730357 -- app/execution_core tests/execution_core work/active/WO-0147-reset-kernel-c-trading-authority-controls.md
git diff --check 1d294e0ac29dcd169a4733df3aa9cbd337dc8787..41c7e956d1c49b450615a03374bd0ef7ee730357
```

The reviewed range may change only declared WO-0147 execution-core source/tests, its active work
order, and preserved REV-0049 request/result history. No accepted ADR, reset-packet record,
legacy/runtime path, store/database, adapter, API/UI, or CI workflow may change.

No credential discovery/use, broker activity, network access, SQL/DDL, database engine/client or
fixture, ORM/schema/migration tool, runtime wiring, push, PR, merge, deletion, or cleanup is needed
or permitted. Pure in-memory Python probes, static inspection, and temporary test-local mutations
that are exactly restored are permitted.

## Required closure attacks

Pre-register concrete counterexamples before reading the repair checkpoints in the work order.

### P0 acceptance-closure provenance

1. The package root and public reducer must expose no caller-mintable acceptance proof/close
   capability. Public submission of an exact close input must fail before mutation.
2. Through direct module-private access, both `CONTRACT_COMPLETE_RESPONSE` and
   `COVERED_RECONCILIATION` must still be inert in M1. Attack `_apply_venue_input` with exact-shaped,
   caller-selected proof metadata and then attempt a fresh final SELL claim. The book/view must be
   unchanged and venue uncertainty must continue blocking dispatch authority.
3. Forge a matching externally closed effect plus matching close input ledger and pass it through
   `_audit_hydrate_book`/constructor reconstruction. It must be rejected; correlation, digest shape,
   and a self-consistent ledger cannot certify adapter/query coverage.
4. Attack the default-deny certification predicate, direct/private aliases, module attributes,
   dynamic import/access, export lists, and production call sites. Underscore naming or `__all__`
   omission is not sufficient. Confirm semantic refusal remains the primary boundary and the AST
   production-name guard is only defense in depth.
5. Exact replay of a previously canonical externally certified close must be inert without
   re-certification, while changed content under the same input ID must remain `CONFLICT`. Replay
   ordering must not provide a fresh close capability or transfer authority between books.
6. Reducer-owned `NEVER_DISPATCHED` closure must still require canceled-before-dispatch, no claim
   occurrence, no immutable claim, and no active leg; it must round-trip through hydration.
7. Test-only future-M2 simulation must remain narrowly scoped to tests. No shipping token, boolean,
   hook export, caller-supplied verifier, or other ordinary production mint may enable the predicate.

### P1 query phase

8. A new query claim is admitted in exactly `RECONCILING` and `SERVING`, and refused in
   `BOOTSTRAPPING`, with no budget/index/venue/claim mutation on refusal.
9. Permanent query identity replay/conflict precedes mutable phase policy. Exact replay remains
   inert and changed replay remains conflict after phase drifts to `BOOTSTRAPPING`.
10. Attack direct construction/hydration, wrong types/enums, phase drift, budget boundaries, and
    alternate entry points for a bypass or partial mutation.

### P1 manual-flatten lifecycle

11. From `SELL_CREATED`, only the exact residual-stale, unclaimed, ownerless,
    reconciliation-clean local manual SELL may retire. Retirement must atomically restore the same
    workflow to `READY`, debit no budget, mint no claim, and retain all permanent tombstones.
12. Claimed SELL, unchanged residual, scope mismatch, or unresolved same/cross-symbol venue work
    must refuse retirement. No target exemption may hide a sibling or account-wide blocker.
13. A fresh replacement must use fresh identities, re-read residual, pass ordinary create/final
    gates, and claim once only. Retired identity replay/reuse cannot resurrect or double-claim work.

### Regression, fixture, and scope attacks

14. No change weakens kill, mode, fence, session, budget, binding, residual, venue uncertainty,
    parent closure, cancellation reservation, hydration validation, or bounded-index behavior.
15. Compatibility fixtures that simulate future certified closure must not mask the default-deny
    negative controls, leak monkeypatch state, normalize a production call path, or let stateful
    models prove a different contract than shipping M1.
16. Every protected production-name spelling must be pinned and failure-capable. Attempt removal of
    one denylist member and a semantic mutation that moves certification before replay.
17. The repair remains pure, deterministic, unwired, and within declared paths. No operational
    success, database result, broker behavior, or author full-suite claim may be used as proof of
    these pure semantics.

## Minimum fresh evidence

Run at least four novel pure probes:

- strongest reachable caller-authored private close, followed by a final-claim attempt;
- matching forged closed-effect/input-ledger hydration;
- exact replay and changed same-ID conflict after test-modeled certification has ended; and
- late residual replacement or permanent query-ID conflict after disallowed phase drift.

Run at least two independent failure-capability controls without leaving the target modified: one
semantic closure/replay mutant and one production-name-boundary mutant. Record baseline/final hashes.

At minimum reproduce with `BROKER_ADAPTER=mock` and cache writes disabled:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_venue_provenance_hardening.py tests/execution_core/test_authority.py tests/execution_core/test_authority_stateful.py --maxfail=1
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core --maxfail=1
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
.\.venv\Scripts\lint-imports.exe
```

The author full-repository coverage run is not a required independent gate for this pure addendum.
Do not report it as reproduced unless actually rerun. External exact-head Python 3.11/3.12 CI is a
separate post-review closeout gate.

## Result contract

For each original REV-0049 P0/P1 and the later private reducer/hydration P0, state `CLOSED` or
`OPEN` with exact `file:line` evidence and fresh counterexample outcome. Promote each new P0/P1
separately with impact and smallest resolution. State every item not verified.

`ACCEPT` requires all four obligations closed and no new unresolved P0/P1. Even `ACCEPT` does not
close WO-0147 before disposition, Fable/ledger/PKL closeout, one final immutable push, and unchanged
exact-head Python 3.11/3.12 CI.
