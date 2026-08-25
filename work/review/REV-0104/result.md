# REV-0104 result — WO-0168c root-remediation exact-source review

Date: 2026-08-25
Review mode: fresh-context, findings only, source/static only
Frozen commit: `cdf17715839d7d109dbf555cb4064488ae0beefe`
Frozen tree: `d6304912ca316552272d6379936cc6a1d661ade8`
Frozen source blob: `5b1367e08e723a9edac5b02f9b7e799b7d68602f`

## Findings

### P0-1 — callable scope maps lose provenance through returned maps

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:2193` and
`:6135` in the frozen blob.

Both scanners accept a local function returned through `globals()` and then
looked up through `dict(expose())`. The map resolver recognizes direct namespace
factories but does not retain the returned map kind across a callable boundary.
This matters because a deferred function can acquire a protected module after
the scanner has treated its activation as ordinary.

Minimal shape:

```python
TARGET = "helper"
def probe(): return import_module(TARGET).install_schema
def expose(): return globals()
dict(expose())["probe"]()
TARGET = "json"
```

Resolve by propagating finite callable return alternatives into namespace-map
resolution, including the one-argument `dict` copy, in both scanners.

### P0-2 — incomplete-import mutation ownership is lost through module maps and bound mutators

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:3161` in
the frozen blob.

An unresolved dynamic import is conservatively owned as `incomplete-import`,
but `.__dict__` and bound `.__setattr__`/`.__delattr__` do not preserve that
ownership. Direct and map mutation can therefore be accepted even though the
runtime target may be the approval module.

Minimal shapes:

```python
module = import_module(choose_target())
module.__dict__["APPROVED_EXECUTION_DDL_SHA256"] = "forged"
module.__setattr__("ordinary_member", "forged")
```

Resolve by assigning an owned incomplete-module-map kind and an owned bound
mutator kind, then rejecting every mutation whose target remains incomplete.

### P0-3 — unresolved dynamic imports stop being protected cross-file carriers

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:5420` in
the frozen blob.

The topology fixpoint records `dynamic-import` but omits it from the carrier
set. Exporting such a value through a relay module therefore makes a later
protected member access appear ordinary.

```python
# relay.py
carrier = import_module(choose_target())
# consumer.py
from relay import carrier
carrier.install_schema
```

Resolve by retaining `dynamic-import` as a may-carry-protected value through
exports and the cycle-safe fixpoint.

### P0-4 — `sys.modules` lookup owns only an exact module, not a protected package prefix

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:5592` in
the frozen blob.

The topology map lookup checks exact module identity only. A loaded protected
child can be reached from its package object without retaining the child
provenance.

```python
import tests.execution_core.package.helper
package = sys.modules["tests.execution_core.package"]
package.helper.install_schema
```

Resolve by applying the same exact-or-prefix module classification used by
dynamic imports to static `sys.modules` keys.

### P0-5 — trace callback safety is lexical rather than effect-closed

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:3661` in
the frozen blob.

The callback walk rejects explicit calls and attribute/subscript writes inside
the callback, but still accepts operations that can invoke arbitrary behavior
implicitly and does not prove the callback object or a captured counter remains
immutable after definition. Accepted examples include replacing
`trace.__code__`, reading `attacker[0]` in the callback, and rebinding a
nonlocal counter to an arbitrary object before `+= 1`.

Resolve with a closed callback statement grammar, exact immutable counter
ownership, and whole-scope callback-reference closure rather than another list
of dangerous member names.

### P1-1 — the clean inventory depends on a filename-specific mutation waiver

Evidence: reproduced source-only.
Location: `tests/execution_core/test_persistence_write_capability.py:3990` in
the frozen blob.

The scanner explicitly permits one `monkeypatch.setattr` in
`test_persistence_schema.py`. That makes the claimed finite grammar depend on a
route-specific exception in the exact area it is intended to govern.

Resolve by removing the mutation from the held test design and proving digest
refusal/order through a pure private guard plus source-order control; remove the
waiver entirely.

### P1-2 — Boolean and incomplete-target controls are not mutation-independent

Evidence: reproduced source-only by deleting the intended alternative-union or
completeness branch and observing existing generic diagnostics still satisfy
the broad assertions.
Location: `tests/execution_core/test_persistence_write_capability.py:11125` and
`:11386` in the frozen blob.

Resolve with controls whose acceptance changes only when the targeted Boolean
alternative or incomplete-target rule is removed, and assert the owning
diagnostic where the primary scanner exposes one.

## Reconciliation and limits

The findings above are deduplicated by owning defect. No pytest suite, project
module, SQLite module, connection, database, or DDL was executed. Minimal AST
strings were evaluated only by the two source scanners. A second reviewer seat
was attempted twice but the platform stopped it with a false-positive content
classification before it returned a verdict; that seat contributes no evidence
to this result.

P0: 5
P1: 2
P2: 0

## Verdict

`BLOCK`

The changed-DDL HUMAN-GATE remains closed. A successor must correct these roots
and receive a fresh exact-source review with `P0=0` and `P1=0`.
