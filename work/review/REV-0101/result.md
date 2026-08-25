# REV-0101 result — WO-0168c finite-state provenance review

Date: 2026-08-25
Frozen source target: `2189d0fe6cf5428188b83255a5ef7725fac61174`
Frozen source tree: `a068104c1f9363b6557f8f41b69c980dcb605976`
Review seats: two fresh-context GPT-5.6 Sol Max reviewers; findings below are
deduplicated by owning defect.

## Findings

### P0-1 — expression-level conditional assignments are recorded as definite

`tests/execution_core/test_persistence_write_capability.py:1734`

A walrus assignment in a skipped short-circuit operand replaces prior governed
provenance even though Python may never execute it:

```python
import sqlite3
True or (sqlite3 := object())
sqlite3.connect("blocked.db")
```

`_is_conditional_binding` recognizes statement control flow but not `BoolOp`
or conditional-expression operands. The skipped ordinary assignment therefore
erases `module:sqlite3`, allowing the connection route to disappear.

Resolve expression-level execution precisely enough to retain prior state for
short-circuit/conditional operands while not marking an always-evaluated test
or first boolean operand conditional. Apply the same rule to both binding
tables and add a failure-capable control.

### P0-2 — lambda bodies use final parent state instead of call-time state

`tests/execution_core/test_persistence_write_capability.py:1940`

`ast.Lambda` is a function scope but is excluded from deferred callable
observation:

```python
import sqlite3
run = lambda: sqlite3.connect("blocked.db")
run()
sqlite3 = object()
```

The lambda falls through to final-module binding selection, so the later
ordinary state erases the SQLite state visible at `run()`.

Resolve both named and anonymous callable identity through direct bindings and
simple aliases, then evaluate parent bindings at proven calls. Use conservative
future states only after a real value-flow escape.

### P0-3 — `ImportFrom` namespace-package aliases lose package-prefix identity

`tests/execution_core/test_persistence_write_capability.py:3896`

With a helper exporting the approval accessor, this consumer is unresolved:

```python
from tests import execution_core as package
package.helper.require_approved_ddl_execution
```

`tests.execution_core` has no `__init__.py`, so exact module lookup returns no
kind. The `ImportFrom` branch does not try module-prefix lookup and records
`package` as ordinary, erasing the protected helper path.

Apply package-prefix resolution to imported submodules, including namespace
packages, and add the exact adjacent spelling as a topology control.

### P0-4 — the ordinary-member allowlist exposes mutable import machinery

`tests/execution_core/test_persistence_write_capability.py:2343`
`tests/execution_core/test_persistence_write_capability.py:2486`

`sys.path` is classified as ordinary, allowing source to prepend an alternate
approval-module location before using the canonical import spelling:

```python
import sys
sys.path.insert(0, "attacker")
from approved_schema_digest import require_approved_ddl_execution
```

Remove mutable/import-affecting members from the ordinary allowlist. Permit
only exact current read operations; an unmodeled module member or method escape
must retain governed provenance and fail closed.

### P0-5 — the conditional-target control cannot kill its intended mutation

`tests/execution_core/test_persistence_write_capability.py:7680`
`tests/execution_core/test_persistence_write_capability.py:2415`

The SQLite-versus-JSON conditional target still fails when all alternatives
are discarded because `.connect` on `unknown-dynamic` independently becomes a
connection reference. Its broad `assert violations` therefore cannot prove
static-alternative preservation.

Use an isolating approval-module-versus-ordinary target and assert the exact
approval-provenance diagnostic. Removing alternative propagation must make
that control fail.

### P1-1 — passive observations and simple local aliases are treated as escape

`tests/execution_core/test_persistence_write_capability.py:1981`
`tests/execution_core/test_persistence_write_capability.py:1992`

An identity comparison or simple alias assignment causes the callable to be
treated as escaped from function definition onward, retaining a protected
state no call can observe:

```python
import sqlite3
def connect(path):
    return sqlite3.connect(path)
alias = connect
sqlite3 = ordinary_transport
alias("ordinary.resource")
```

The same false positive occurs with `connect is connect` followed by the
definite ordinary rebind and direct call. Track simple callable aliases and
their call positions. Ignore passive identity observations; classify only
actual return, argument, container, attribute/subscript storage, or otherwise
unowned value flow as escape. If a real escape occurs, begin the conservative
future-state union at the escape position, not function definition.

## Evidence and limits

- Both seats reviewed the exact frozen source identity and returned source-
  reasoned minimal mutants.
- No reviewer executed mutant text, pytest, or any held suite.
- Reviewers did not import project modules or SQLite, open a database, install
  DDL, or recompute DDL/catalog/manifest identities.
- The author's exact-head Ruff, AST, mypy, import-linter, governance, scope,
  whitespace, and source-text identity evidence remains separately recorded;
  reviewers did not rerun it.

## Verdict

`BLOCK` — P0=5, P1=1, P2=0.

The changed-DDL HUMAN-GATE remains closed. A successor exact source target
requires a fresh independent P0=0/P1=0 review.
