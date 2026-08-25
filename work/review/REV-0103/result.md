# REV-0103 result — WO-0168c runtime-provenance source review

Date: 2026-08-25
Frozen source target: `6dd9396093a58f8e6025521146aa99534a74f01c`
Frozen source tree: `ce749e17c1a31b141a871783136f53e803b2a62c`
Review seats: two fresh-context GPT-5.6 Sol Max reviewers; findings below are
deduplicated by owning defect.

## Findings

### P0-1 — assignment targets are resolved before their runtime RHS phase

`tests/execution_core/test_persistence_write_capability.py:1820`
`tests/execution_core/test_persistence_write_capability.py:1832`
`tests/execution_core/test_persistence_write_capability.py:4188`
`tests/execution_core/test_persistence_write_capability.py:4202`

For `Assign` and valued `AnnAssign`, Python evaluates the right-hand side before
the target operation. The scanners can resolve a capability-bearing target from
its earlier lexical position and miss a walrus binding performed by the RHS.

```python
TARGET = "json"
import_module(TARGET).APPROVED_EXECUTION_DDL_SHA256 = (
    TARGET := "approved_schema_digest"
)
```

Resolve assignment expression/target phases explicitly in both scanners.

### P0-2 — finite namespace lookup hides early callable activation

`tests/execution_core/test_persistence_write_capability.py:2186`
`tests/execution_core/test_persistence_write_capability.py:2259`
`tests/execution_core/test_persistence_write_capability.py:4886`
`tests/execution_core/test_persistence_write_capability.py:4959`

A local function invoked through a statically resolvable `globals()`/`vars()`
map is not recognized as a call or escape. Its body can therefore be analyzed
under a later safe module-final binding instead of the earlier protected state.

```python
TARGET = "sqlite3"
def probe():
    return import_module(TARGET).connect("blocked.db")
globals()["probe"]()
TARGET = "json"
```

Preserve callable identity through finite namespace/map lookups and treat an
unresolved indirect activation as escape/conservative activation.

### P0-3 — helper protection is not transitive through child or governed modules

`tests/execution_core/test_persistence_write_capability.py:3984`
`tests/execution_core/test_persistence_write_capability.py:4548`
`tests/execution_core/test_persistence_write_capability.py:4592`

`_owner_has_protected` sees only direct protected values. It misses a helper
that exports a protected child module and misses whole governed modules such as
`builtins`, `sys`, or `importlib`. A downstream consumer can recover the
importer, trace setter, or approval accessor without relayed provenance.

Resolve this with one cycle-safe `may_carry_protected` fixpoint spanning local
modules/maps, package prefixes, governed modules, members, aliases, and calls.

### P0-4 — trace callbacks can replace themselves through `nonlocal`

`tests/execution_core/test_persistence_write_capability.py:3163`
`tests/execution_core/test_persistence_write_capability.py:3169`
`tests/execution_core/test_persistence_write_capability.py:3210`

The trace-body check rejects `global` but not `nonlocal`, permits callback-name
assignment, and accepts self-return by spelling. A callback can replace its
closure binding with a malicious sibling and return that function.

Reject `Nonlocal` and callback/closure writes or deletes, and prove self-return
against immutable function identity rather than only a name spelling.

### P0-5 — literal dynamic namespace-package imports lose prefix identity

`tests/execution_core/test_persistence_write_capability.py:5202`

`_module_from_importer` calls only `_module_kind(target)`. A complete literal
such as `import_module("tests.execution_core")` therefore loses prefix/map
provenance and can recover an attached protected helper.

Use exact-or-prefix classification in every import-target resolver and retain
that identity through aliases, maps, reflection, and child lookup.

### P0-6 — incomplete import owners can mutate a protected member

`tests/execution_core/test_persistence_write_capability.py:2872`
`tests/execution_core/test_persistence_write_capability.py:2876`

An unresolved import target becomes ordinary `unknown-dynamic`. Attribute
classification recognizes the approval-token member, but mutation diagnostics
inspect only the unprotected owner and emit no violation.

```python
TARGET = choose_target()
import_module(TARGET).APPROVED_EXECUTION_DDL_SHA256 = "forged"
```

Preserve incomplete-import provenance and inspect both owner and resolved
protected-member identity at direct, map, alias, and `getattr` mutation sinks.

### P1-1 — discarded deferred objects are treated as body activation

`tests/execution_core/test_persistence_write_capability.py:2186`
`tests/execution_core/test_persistence_write_capability.py:2262`
`tests/execution_core/test_persistence_write_capability.py:4886`
`tests/execution_core/test_persistence_write_capability.py:4962`

Creating and discarding a generator, generator expression, or coroutine object
does not execute its body, but the model conservatively acts as if it does.
Separate deferred-object creation from finite iteration, `next`, `await`, or a
genuine escape.

### P1-2 — unguarded irrefutable captures retain impossible prior state

`tests/execution_core/test_persistence_write_capability.py:1680`
`tests/execution_core/test_persistence_write_capability.py:1861`
`tests/execution_core/test_persistence_write_capability.py:4231`
`tests/execution_core/test_persistence_write_capability.py:4282`

An unguarded whole-subject `case TARGET` is definite, but both scanners mark all
case bindings conditional. Treat only this irrefutable unguarded capture as a
definite subject binding; guarded, refutable, and extracted captures remain
conditional.

### P1-3 — accepted trace installation has no required restoration lifecycle

`tests/execution_core/test_persistence_write_capability.py:3227`

A safe callback may be installed and never restored. Require the finite exact
lifecycle: capture `sys.gettrace()`, install the validated immutable callback,
and restore that exact captured value in `finally`; reject missing, late,
conditional, or mismatched restoration.

### P1-4 — ordinary namespace metadata can become protected after relay

`tests/execution_core/test_persistence_write_capability.py:4675`

An exact ordinary key such as `package.__dict__["__name__"]` can become a
generic protected member and then be rejected downstream. Preserve
prefix-specific unknown provenance and protect it only where that prefix may
contain a governed descendant; pin ordinary metadata reads as accepted.

### P1-5 — trace rejection branches lack independent mutation proof

`tests/execution_core/test_persistence_write_capability.py:3163`
`tests/execution_core/test_persistence_write_capability.py:3184`

Current controls do not independently kill removal of callback import rejection
or callback call rejection. Add exact-diagnostic controls for import-only,
call-only, callback escape, and non-`gettrace` restoration mutants.

### P1-6 — Boolean and incomplete-target branches lack independent mutation proof

`tests/execution_core/test_persistence_write_capability.py:2406`
`tests/execution_core/test_persistence_write_capability.py:2416`

Add source and topology controls that independently kill removal of Boolean
alternative unioning and of the completeness bit for a protected-plus-unknown
target. Require the intended approval/schema diagnostic.

## Evidence and limits

- Both seats verified the frozen identity and independently performed
  source-only, failure-capable review.
- No reviewer ran pytest, imported project modules or SQLite, opened a database,
  installed DDL, used network access, or changed the worktree.
- Author Ruff, AST, mypy, import-linter, governance, scope, whitespace, and
  source-only identity evidence was not independently rerun by the review seats.

## Verdict

`BLOCK` — P0=6, P1=6, P2=0.

The changed-DDL HUMAN-GATE remains closed. A successor exact source target
requires a fresh independent P0=0/P1=0 review.
