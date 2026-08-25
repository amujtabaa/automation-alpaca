# REV-0102 result — WO-0168c conditional/callable provenance review

Date: 2026-08-25
Frozen source target: `501a86425c32ab8b099f897f23334cbbc0df5b36`
Frozen source tree: `df69b207a0b4c060187deaf7e270ef334c0984aa`
Review seats: two fresh-context GPT-5.6 Sol Max reviewers; findings below are
deduplicated by owning defect.

## Findings

### P0-1 — finite conditional bindings omit comparison, with-item, and pattern semantics

`tests/execution_core/test_persistence_write_capability.py:1654`
`tests/execution_core/test_persistence_write_capability.py:1745`
`tests/execution_core/test_persistence_write_capability.py:1800`
`tests/execution_core/test_persistence_write_capability.py:3827`

Both scanners can erase a protected binding through a skipped comparator in a
chained comparison. They also treat a later `withitem.optional_vars` binding as
definite even though a previously entered suppressing manager can absorb the
later manager's failure before assignment. Match captures (`MatchAs`,
`MatchStar`, and mapping rest) never enter either binding table at all.

Minimal representatives:

```python
TARGET = "sqlite3"
0 > 1 < (TARGET := "ordinary")
import_module(TARGET).connect("blocked.db")
```

```python
TARGET = "json"
match "sqlite3":
    case TARGET:
        pass
import_module(TARGET).connect("blocked.db")
```

Resolve with one shared execution-child rule for chained comparisons and each
with-item phase, plus real-owner conditional pattern bindings. A simple whole-
subject capture may preserve the subject expression; extracted captures must
remain governed-unknown unless proven ordinary.

### P0-2 — finite conditional import expressions lose protected alternatives

`tests/execution_core/test_persistence_write_capability.py:2189`
`tests/execution_core/test_persistence_write_capability.py:2654`
`tests/execution_core/test_persistence_write_capability.py:4508`
`tests/execution_core/test_persistence_write_capability.py:4587`

Literal `IfExp` and Boolean import targets resolve to an empty/incomplete state.
The importer becomes generic `unknown-dynamic`, whose sensitive-member handling
does not retain approval-token provenance:

```python
import_module(
    "approved_schema_digest" if condition else "json"
).APPROVED_EXECUTION_DDL_SHA256 = "ab" * 32
```

Resolve by carrying every finite literal alternative and its completeness bit.
An incomplete importer must independently fail closed when a sensitive approval,
schema, SQLite, or protected-topology member is accessed or mutated.

### P0-3 — lexical source positions are not callable execution timestamps

`tests/execution_core/test_persistence_write_capability.py:1786`
`tests/execution_core/test_persistence_write_capability.py:2022`
`tests/execution_core/test_persistence_write_capability.py:2042`
`tests/execution_core/test_persistence_write_capability.py:2096`
`tests/execution_core/test_persistence_write_capability.py:4355`
`tests/execution_core/test_persistence_write_capability.py:4433`

Four manifestations share one unsound timing rule:

- closure state is sampled at the start of a call, before argument-side walrus
  assignments execute;
- `global`/`nonlocal` writes inside a callable are placed on the owner's lexical
  timeline, allowing a later body write to erase an earlier body read;
- a returned/escaped nested callable or method is collapsed to its factory/class
  activation and can execute under later parent state; and
- generator, async-generator, and coroutine creation is treated as body
  execution even though the body starts only at iteration/await.

Representative bypasses include `probe(TARGET := "sqlite3")`, a function that
reads global `TARGET` before assigning it ordinary, a factory returning a lambda
called after a protected rebind, and a generator resumed after such a rebind.

Replace the timestamp rule at the contract level. Only a proven synchronous
direct call may narrow state, and its body-entry observation must follow ordered
argument evaluation. Unproven, returned, method, generator, coroutine, and
owner-write timing must remain conservative from the real escape/creation point
instead of borrowing an enclosing lexical line.

### P0-4 — governed module members lose provenance through `ImportFrom`

`tests/execution_core/test_persistence_write_capability.py:1837`
`tests/execution_core/test_persistence_write_capability.py:2429`
`tests/execution_core/test_persistence_write_capability.py:4006`
`tests/execution_core/test_persistence_write_capability.py:4048`

`from sys import path` is recorded ordinary because unknown members of a
governed module do not pass through the attribute classifier. A helper relay
preserves that erasure. The remaining ordinary allowance for `sys.settrace`
likewise exposes interpreter/frame mutation capable of replacing the imported
approval accessor.

Route every governed-module `ImportFrom` member through the same fail-closed
member classifier used for attribute access, preserve it through helper relays,
and remove interpreter-mutating members from the ordinary read set.

### P0-5 — namespace-package prefixes lack governed map/reflection semantics

`tests/execution_core/test_persistence_write_capability.py:4108`
`tests/execution_core/test_persistence_write_capability.py:4145`

An `ImportFrom` namespace-package alias now retains a `module-prefix`, but
`__dict__`, `__class__`, `__getattribute__`, loaders, mutators, and escape logic
apply only to exact module/local kinds. `package.__dict__["helper"]` therefore
becomes ordinary and can recover a protected helper accessor and its globals.

Give module prefixes the same governed namespace-map, descriptor, loader,
mutator, and escape ownership as exact modules. Static child lookups may resolve
exact/prefix descendants; dynamic or reflective use must fail closed when a
protected descendant is possible.

### P1-1 — a passively discarded local walrus alias is classified as escape

`tests/execution_core/test_persistence_write_capability.py:1992`
`tests/execution_core/test_persistence_write_capability.py:4323`

`(alias := probe)` as a bare expression is a local owned alias whose result is
discarded. It is currently treated as outward escape, retaining a protected
state even when the only later alias call follows a definite ordinary rebind.
Recognize this exact passive ownership while preserving escape when either the
walrus value or target flows outward.

### P1-2 — an uncalled, unescaped local body falls back to final parent state

`tests/execution_core/test_persistence_write_capability.py:2120`
`tests/execution_core/test_persistence_write_capability.py:4459`

When a non-module callable has no proven call or real escape, the fallback
evaluates its body under final parent state. A passive identity observation of
an otherwise unused function can therefore report an unreachable protected
operation. Represent a genuinely unobservable local body as unobserved; retain
module-final availability only when the callable itself remains externally
reachable.

## Evidence and limits

- Both seats verified the frozen commit/tree/blob and independently returned
  source-reasoned minimal mutants.
- Mutants were source-only AST-parsed by the reviewers; gate functions were not
  executed.
- No reviewer ran pytest, imported project modules or SQLite, opened a database,
  installed DDL, or changed the worktree.
- Author Ruff, AST, mypy, import-linter, governance, scope, whitespace, and
  source-only identity evidence was not rerun by the review seats.

## Verdict

`BLOCK` — P0=5, P1=2, P2=0.

The changed-DDL HUMAN-GATE remains closed. A successor exact source target
requires a fresh independent P0=0/P1=0 review.
