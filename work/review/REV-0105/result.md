# REV-0105 result — WO-0168c exact static-gate successor review

Date: 2026-08-25
Review mode: two fresh Max seats, findings only, source/static only
Frozen commit: `fa260c77fb8d4b54fd915684254e1922eb9ae90a`
Frozen tree: `8599f65b3479f0f575b1b33da77d7fcefdd4e650`

## Findings

### P0-1 — writes through scope maps do not update binding provenance

Evidence: reproduced source-only by both scanners.

`globals()["TARGET"] = "sqlite3"` can change a previously ordinary import
target before `import_module(TARGET).connect(...)`, while both scanners retain
the stale ordinary binding. Callable-returned maps behave the same way.

Root resolution: model every owned scope-map write/mutator as a binding effect,
or fail closed on such mutation as one semantic class.

### P0-2 — callable/deferred returns and copied maps lose ownership

Evidence: reproduced source-only in both scanners.

Immediately activated functions/lambdas returning incomplete imports are
accepted. Activated generator/coroutine scope-map returns, one-argument `dict`
copies, starred copies, `.copy()`, and map unions can likewise recover a
protected callable without retaining provenance.

Root resolution: use one observation model for ordinary calls, generator
iteration, coroutine awaiting, callable returns, and map-copy operations;
propagate every result alternative through the local and cross-file fixpoints.

### P0-3 — incomplete imports escape through dynamic member reflection

Evidence: reproduced source-only in both scanners.

Dynamic `getattr`/`__getattribute__` on an incomplete import can select a bound
mutator at runtime without preserving incomplete-module ownership.

Root resolution: unresolved members of an incomplete import remain owned
through all reflection forms and cannot become ordinary callables.

### P0-4 — exact regular packages shadow protected descendants

Evidence: reproduced source-only.

The package-prefix control works only while `package/__init__.py` is absent. An
empty ordinary `__init__.py` makes the exact package object win over its
protected child; `sys.modules[package].helper.install_schema` is then accepted.

Root resolution: exact package objects must merge their runtime descendant
module members instead of replacing prefix topology.

### P0-5 — reflected trace setters do not enter the lifecycle grammar

Evidence: reproduced source-only.

Static reflection such as `getattr(sys, "settrace")` and
`sys.__dict__["settrace"]` is accepted without the capture/install/protected
`try`/exact-restore proof required for direct `sys.settrace`.

Root resolution: every owned static route to the setter resolves to the same
`trace-setter` identity and is governed by one lifecycle rule.

### P0-6 — callback and filename-filter safety is spelling-based

Evidence: callback/filter map mutation reproduced source-only; canonical
`inspect` concern reasoned-only.

`globals()`/`vars()` aliases can replace the callback code or mutate/clear the
filename-filter set after validation. The filter grammar also trusts the name
`inspect` without proving the canonical immutable module binding.

Root resolution: close callback/filter objects by resolved binding identity,
including scope-map recovery, and prove the exact canonical `inspect` source of
the inert string/`None` filename set.

### P0-7 — the protected interval may disable tracing

Evidence: reasoned-only against the candidate rule that marks every
`settrace(None)` safe.

Disabling tracing inside the measured `try` can produce a falsely bounded line
count and still restore the prior callback afterward.

Root resolution: no trace-state change is safe outside the one complete owned
lifecycle; nested/interval changes must be refused.

### P1-1 — discarded deferred bodies can be reported as executed

Evidence: reproduced source-only.

Creating and discarding a generator/coroutine whose body contains an incomplete
protected route can emit a capability diagnostic even though Python has not
executed that body.

Root resolution: distinguish deferred creation, activation, and escape in the
same observation model used by P0-2.

### P1-2 — constant Boolean short-circuiting is not modeled

Evidence: reproduced source-only.

`"json" or choose_target()` is classified incomplete even though the second
operand is unreachable.

Root resolution: apply compile-time truthiness to reachable Boolean operands
before unioning target alternatives.

### P1-3 — digest purity/order control is not failure-capable

Evidence: reproduced source-only by an effectful guard condition that still
contains a mismatch comparison and raise.

Root resolution: pin the helper to one exact `approved != actual` condition and
one exact exception raise, with no other calls or effects.

### P1-4 — the exact counter increment accepts non-integers

Evidence: reasoned-only.

The condition `value == 1` also accepts `1.0`, `True`, and `1+0j`.

Root resolution: require exact non-Boolean `int` type and value `1`.

### P1-5 — callback closure conflates unrelated same-spelled names

Evidence: reproduced source-only.

An unrelated function parameter named `trace` makes an otherwise accepted
lifecycle fail because the candidate searches the whole module by spelling.

Root resolution: resolve each load to its binding scope/object identity before
classifying it as a callback reference.

## Reconciliation and limits

The findings above deduplicate both reviewers by shared semantic owner. No
pytest suite, project module, SQLite module, connection, database, or DDL was
executed. Reviewers used only source inspection and minimal in-memory strings
passed to the scanners. The implementation seat's 30 controls and two 49-file
inventories remain valid author evidence but do not disprove the new examples.

P0: 7
P1: 5
P2: 0

## Verdict

`BLOCK`

The changed-DDL HUMAN-GATE remains closed. A successor requires fresh exact
review with `P0=0` and `P1=0`.
