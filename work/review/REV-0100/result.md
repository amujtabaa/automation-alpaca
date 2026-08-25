# REV-0100 result — WO-0168c replacement finite-provenance review

Date: 2026-08-25
Frozen source target: `97f316b934114f0b70f9fd2975c276a6b37e272b`
Frozen source tree: `c5534f689a1571107b63f83f819c48763c15909d`
Review seats: two fresh-context GPT-5.6 Sol Max reviewers, independently bounded; findings below are deduplicated by owning defect.

## Findings

### P0-1 — finite provenance stops at derived attributes and namespace maps

`tests/execution_core/test_persistence_write_capability.py:2168`
`tests/execution_core/test_persistence_write_capability.py:2189`
`tests/execution_core/test_persistence_write_capability.py:2599`
`tests/execution_core/test_persistence_write_capability.py:3598`
`tests/execution_core/test_persistence_write_capability.py:4144`

Reproduced AST-only mutants returned no violation for dynamic
`vars(builtins)[name]` recovery of `__import__`,
`schema.__builtins__["__import__"]`, helper `__loader__` recovery, helper
`__setattr__`, and helper `__dict__.update`. The module value is owned, but an
unmodeled attribute or derived namespace map becomes ordinary. That permits
SQLite/schema recovery or mutation of a protected helper export.

Resolve at the provenance type: unknown governed attributes and dynamic reads
from governed maps must produce governed-unknown; helper maps and bound/module-
type mutators remain protected values; arbitrary helper members fail closed
instead of being assumed ordinary. Add failure-capable getter, map, loader,
bound-mutator, and map-mutator controls.

### P0-2 — package aliases and conditional static alternatives lose identity

`tests/execution_core/test_persistence_write_capability.py:3504`
`tests/execution_core/test_persistence_write_capability.py:3828`

`import tests.execution_core as package` loses module-prefix identity when an
alias is present, so `package.helper` becomes ordinary. A statically known
conditional target set such as `{"helper", "ordinary"}` is collapsed to no
target, erasing the protected alternative. Both produce zero topology
violations while recovering the approval accessor.

Resolve by retaining module-prefix identity for aliased package imports and by
propagating every statically known text alternative. Any protected alternative
must remain protected; an unconditional later binding may replace earlier
states only when source order proves it.

### P0-3 — deferred and declared-owner binding semantics diverge from Python

`tests/execution_core/test_persistence_write_capability.py:1885`
`tests/execution_core/test_persistence_write_capability.py:1950`
`tests/execution_core/test_persistence_write_capability.py:3479`

A nested function can observe an enclosing `from sys import modules` or static
import target established after the nested body is written but before its call.
The primary scanner considers future governed bindings only at module scope;
the topology scanner does not route `global` and `nonlocal` imports/assignments
to Python's declared owner. The reviewed mutants therefore mutate
`sys.modules`, the approval token, or a helper export with no violation.

Resolve with one declared-owner model for imports and assignments and with
call-observable deferred binding states at every enclosing function/module
scope. Add nested call-after-bind, `global`, and `nonlocal` controls.

### P1-1 — deferred union retains a state no call can observe

`tests/execution_core/test_persistence_write_capability.py:3759`

The remediation unions every parent binding after function definition. It
therefore rejects a function whose only call follows a definite ordinary
rebind. Resolve by evaluating direct call-observable states where call identity
is provable, using conservative alternatives only when the callable escapes or
the call site is not statically owned.

### P1-2 — error-type rewrite can share the lifecycle's shadow

`tests/execution_core/test_protection.py:3396`

The replacement mapping uses the helper module's unqualified `TypeError` and
`ValueError`. Rebinding those names in both the helper and lifecycle modules
lets the assertion accept a fake exception class; the prior builtin lookup
refused it. Resolve with direct `builtins.TypeError`/
`builtins.ValueError` identities and a negative control that shadows both
modules independently.

## Evidence and limits

- Both seats verified the frozen commit/tree, parent/tree, packet blobs, and
  corrected approval-file provenance.
- Both verified the unchanged DDL SHA-256, 178755-byte count, catalog digest,
  R4 manifest, and locked `None` approval literal from source text only.
- The findings above were reproduced with AST-only source mutants; mutant text
  was never executed.
- The worktree remained clean and `git diff --check` passed.
- The author had already recorded 761 CPython 3.12 and 33 CPython 3.14
  held-safe passes; the reviewers did not rerun those matrices before cutoff.
- No reviewer imported SQLite, opened a connection/database, installed DDL,
  or ran a held suite.

## Verdict

`BLOCK` — P0=3, P1=2, P2=0.

The changed-DDL HUMAN-GATE remains closed. A new exact source target requires a
fresh independent P0=0/P1=0 review.
