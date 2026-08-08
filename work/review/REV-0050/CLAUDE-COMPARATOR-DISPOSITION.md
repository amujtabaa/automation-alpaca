# WO-0148 Claude clean-room comparator adjudication

Status: **COMPARATOR CLAIMS RE-DERIVED; THREE CURRENT P1 GAPS ACCEPTED AND REPAIRED**

Comparator source: remote commit `b56ce60043e0609bd73989f8429b573539cedd93`, path
`work/review/REV-0050/claude-clean-room-result.md`. The comparator branch was fetched and read with
`git show`; it was not merged. The packet remains non-authoritative and cannot accept, close, or
advance WO-0148. Each claim below is adjudicated against the active WO, accepted ADRs, and current
tests rather than against the comparator's verdict.

## Blocking findings

### X1 — accepted P1: the lifecycle grammar rejected the required exact `Fraction` guard

Authority: WO-0148 clauses 1 and 8 require exact-type mandate validation and exact `Fraction`
economics. The previous blanket metaclass rule admitted only `type` and `EnumMeta`, while
`type(Fraction)` is `ABCMeta`; the allowed fractions module and `Fraction` operand grammar were
therefore unreachable.

Fresh disproof before repair:

```text
> .\.venv\Scripts\python.exe -c "import runpy; from fractions import Fraction; ns=runpy.run_path('tests/execution_core/test_protection.py'); print(type(Fraction).__name__); print(ns['_lifecycle_global_type'](lambda: Fraction,'Fraction'))"
ABCMeta
AssertionError: lifecycle type target has a custom metaclass: Fraction
```

Repair: admit only the exact standard metaclass identities `type`, `EnumMeta`, and the `ABCMeta`
identity obtained from `type(Fraction)`, then run the existing no-user-attribute-dispatch seal before
reading candidate metadata. The sequential-lifecycle meta control now contains a real exact
`Fraction` guard and rejects `True` as its malformed value.

Restoration evidence:

```text
> .\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_protection.py::test_passive_lifecycle_accepts_exact_sequential_validation
. [100%]
> current direct helper probe
ABCMeta
<class 'fractions.Fraction'>
```

The existing custom-metaclass value-graph mutant still fails, and the active guarded-attribute
mutants still fail before payload execution.

### C4-a — accepted against the seventh freeze; already repaired, now failure-capable in RED

Authority: WO-0148 clause 10 and the RED mutation obligations require same-type, different-value
forgeries rather than wrong-type substitutes killed by input validation.

Fresh reproduction against the exact comparator base loaded the genuine old helper and real kernel
type:

```text
> load 433a5fb:tests/execution_core/test_protection.py and call
> _different_value(MandateId("old-collision"))
TypeError: _clone_opaque() got multiple values for argument 'value'
```

The current helper's positional receiver is named `original`, so a dataclass field named `value`
cannot collide with it. The executable RED meta control now exercises `_different_value` over real
`MandateId`, `PriceUnits`, `ReportedPrice`, and `VenueRecoveryTransition` values and requires an
unequal result of the exact same root type. It also runs the recursive one-leaf walker across all
four real `ReportedPrice` leaves. No exception fallback, generic `object()` substitution, or
wrong-type repair was introduced.

### X2 — accepted P1 for gate integrity; protective power was not weakened

Authority: WO-0148 gate 5 and `.github/workflows/ci.yml` require unchanged Python 3.11 and 3.12
targets. CPython 3.11 does not expose `slots` in `_DataclassParams.__slots__`; unconditionally
indexing `parameter_values["slots"]` made seven meta controls error before assertion.

Adjudication: this is P1 because the declared CI gate could not execute, even though it was an
over-strict failure rather than a false negative. The repair moves `slots: True` into the existing
version-optional parameter loop. The version-independent `namespace["__slots__"] == field_names`
assertion remains unchanged, so a non-slotted value is still rejected.

Local execution is Python 3.12.13; `py -0p` exposes only a separate Python 3.14 installation. No
local Python 3.11 runtime is available, so this disposition does **not** claim a 3.11 pass. The
actual 3.11 restoration remains an unchanged exact-head CI obligation. On 3.12, all selected
passive metadata, lifecycle, custom-metaclass, and descriptor controls pass.

### C4-b — accepted P1: `None -> object()` was a free wrong-type kill

Authority: WO-0148's exhaustive state-authentication mutation obligation must distinguish value /
union authentication from exact-type rejection.

Repair: the generic mutation walker no longer invents an `object()` sentinel for `None`. Every
optional leaf now requires an explicit valid member of its declared union. The executable RED probe
uses `int | None` and proves `None -> 13`. The production-state sweep explicitly uses valid
`ReportedPrice` alternatives for `high_watermark` and `trail`; any additional optional private leaf
without a frozen valid alternative makes the oracle fail closed rather than silently degrading to
a wrong-type mutant.

### C1 — accepted against the seventh freeze; current root repair retained

Authority: passive lifecycle reads must not execute caller- or type-owned capability code. The slot
descriptor check alone did not prove that property.

Fresh old/current comparison used an exact approved-module class with a real slot and custom
`__getattribute__`:

```text
433a5fb helper: accepted <class 'app.execution_core.values.Active'>
current helper: AssertionError: guarded lifecycle type has custom attribute access: Active
```

The current MRO dispatch seal rejects Python-level `__getattribute__` and `__getattr__` definitions
without naively requiring every C-backed type to inherit `object.__getattribute__`. It now governs
both lifecycle guard targets and the trusted-leaf short circuit in the runtime passive-value graph.
Its positive real-kernel trusted types and `TickMetadata`/`PriceUnits` nested lifecycle, plus
negative getattribute/getattr controls, pass without executing the hostile instance payload.

### C2 — accepted against the seventh freeze; current provenance seal retained

Authority: the three public entry points must be the exact source-audited, package-exported
functions and must retain no donated state or wrapper capability.

The current parameterized provenance helper pins exact `FunctionType`, module/global identity,
package-root identity, signature and annotations, no decorators/defaults/closures/function
attributes, and inspected-source/bytecode correspondence. Its wrapper, rebinding, closure, metadata,
and source-swap mutants pass as rejection controls. Interpreter-specific stored code-object details
remain intentionally unpinned.

### C4-c/d — accepted against the seventh freeze; current recursive repair retained

Authority: every independently retained authority leaf must be mutated once without crossing the
venue-book frontier. The current walker recursively traverses dataclasses, tuples, frozensets,
empty containers, and every nested `ReportedPrice`, tick, and scope leaf. An independent path
enumerator and changed-leaf comparator prove completeness and one-leaf locality. The RED meta
control now pins the exact four real `ReportedPrice` paths:

- `units.value`
- `scale.value`
- `tick.tick_units.value`
- `tick.scale.value`

The old first-field-only `_different_value` remains only for top-level envelope pins; it is no
longer the claimed exhaustive-leaf proof.

### Post-comparator refinements retained in the successor freeze

Focused hostile follow-up strengthened the accepted C4 repair without changing its authority. The
walker now authenticates valid optional-union replacements nested inside tuples and frozensets,
uses annotation-typed replacements for empty containers, refuses a saturated same-type frozenset
rather than silently reusing a value, and exercises the second formula-unavailable state where
`armed_hard_bail_trigger` is `None`. These controls prevent collision or empty-container shortcuts
from turning exhaustive leaf authentication into a free wrong-type rejection.

The PEP 562 suggestion remains non-blocking on Claude's counterexample, but the bounded purity
redesign adopted the inexpensive defense: `__getattr__` and `__dir__` module hooks are now rejected
inside the main protection source gate, with an executable dynamic-surface mutant. This is additive
hardening, not a retroactive severity change.

## Advisory claims

- **C3 severity:** the comparator's downgrade is stale against the amended active WO. The current
  contract explicitly requires protocol-free exact rejection at all seven entry-point positions;
  the existing matrix and no-access tripwire remain.
- **PEP 562 additive name:** not a P0/P1 on the presented counterexample. Whole-tree operational-
  capability bans, exact public inventory, and the single public reducer remain the authority.
  No hidden operational path was demonstrated.
- **Additional subclass seals:** not required for every public value constructor. Exact entry-point
  argument types, passive exact MRO/value shapes, and the explicit mandate seal cover the accepted
  boundary. No blocking bypass was demonstrated.
- **Enum internals / extractor spelling / lifecycle simplification:** no proof control is removed in
  this re-gate. Any simplification is a future bounded redesign requiring its own equivalence and
  mutant evidence; it is not a reason to weaken the frozen contract now.
- The comparator's rejection of bytecode-version brittleness and of inadequate semantic coverage
  is accepted; no work is spent reopening either claim.

## Fresh current-worktree evidence

```text
> selected eight provenance, leaf, lifecycle, metadata, effect, and stateful controls
........ [100%]

> complete focused RED contract
collected=290 failed=233 passed=57 exit=1

> predecessor execution-core corpus excluding the three RED files
698/698 passed
```

The 233 RED failures remain exactly 230 deliberate protection-module-absence failures plus three
required inventory/AST/export deltas. Production remains absent. Ruff, format, Python 3.11 grammar,
diff, scope, ADR digest, and current-source effect gates pass; those static gates must be rerun after
the final re-freeze edits.

## Remaining proof boundary

Actual Python 3.11 execution is unverified locally and remains routed to unchanged exact-head CI.
This adjudication is author-seat evidence, not independent acceptance. Production remains barred
until the amended immutable RED candidate receives a fresh independent zero-P0/P1 exact-commit
verdict.
