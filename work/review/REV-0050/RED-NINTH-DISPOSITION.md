# WO-0148 ninth RED review disposition

Status: **ALL NINTH-REVIEW FINDINGS ACCEPTED AND REMEDIATED IN THE NEXT RED CANDIDATE**

The independent ninth-review result in `RED-NINTH-RESULT.md` is preserved unchanged. Its `BLOCK`
verdict remains authoritative for exact commit `706ed536790179fcb673aaedf96b3b728ee33d3c`; this
disposition does not reinterpret that verdict or authorize production. It records the author seat's
acceptance and root remediation of all three P1 findings in the successor worktree.

## Accepted findings and root remediation

1. **P1-1 — incomplete changed-context replay coverage.** The deterministic contract now spans
   `BEST_BID` and `TRADE` with source sequence present and absent. Every cell requires
   `EXACT_REPLAY`, a recursive pre-call state snapshot plus equality and commitment preservation,
   no goal or alert, and a distinct valid successor whose evaluation time lies between the original
   and replay delivery contexts. A registered generated-history action exercises the same replay /
   between-time-successor composition across generated kind and sequence forms, and the directed
   history invokes the prior missing `TRADE`/sequence-absent cell.
2. **P1-2 — pattern-capture binding laundering.** The protection binding inventory now includes
   assignment/delete targets, every argument, exception targets, `MatchAs`, `MatchStar`, and
   `MatchMapping.rest`, while duplicate module declarations and import/declaration collisions are
   refused. Direct `object.__getattribute__` capability access is no longer allowed. The exact
   reviewer match-capture/output counterexample and separate star, mapping-rest, and exception-name
   captures are failure-capable mutants.
3. **P1-3 — unmodelled writes and persistent hidden state.** A protection-specific write grammar
   now refuses global/nonlocal, named-expression, nested-function/lambda, async/suspended,
   context-manager, delete, augmented, attribute, and subscript mutation forms, plus persistent
   mutable defaults and retained mutable module/class bindings. `object.__setattr__` is accepted only
   as a literal-field write in a straight-line constructor for one uniquely bound fresh local
   `PositionProtectionState` or `ProtectionVenueProjection`; every declared field must be written
   exactly once before a single direct return, with no alias or escape. Exact module-list, global,
   closure/default, caller-input-setter, attribute/subscript, alias, undeclared-field, and context-
   manager mutants fail. A positive skeleton proves both opaque result types remain constructible.

## Hostile iterative pre-flight

A separate Terra pre-flight initially found one additional concrete P1: `with state:` could invoke
an implicit external context-manager capability without an `ast.Call`. `ast.With` and
`ast.AsyncWith` are now refused and a focused mutant pins the failure. The same seat then re-ran the
attack, verified both positive opaque builders, and returned `ACCEPT` with zero remaining P0/P1.
It also identified and the author removed one duplicate setter diagnostic pass as needless P2
complexity. This iterative verdict is current-worktree evidence only, not exact-commit acceptance.

## Fresh successor evidence

- Complete focus: **290 collected / 233 expected RED failures / 57 passes**. The first 230 failures
  are caused by deliberate protection-module absence; the remaining three are the required module-
  inventory, AST/import, and package-export deltas. No helper or meta-oracle fails.
- Predecessor preservation: **698/698 passed** with the three deliberate RED files excluded.
- The focused binding/write mutant matrix and stateful high-risk registration controls pass.
- Ruff check and format-check, Python 3.11 grammar parse, `git diff --check`, activation-base scope
  check, all three accepted ADR digests, and the eight-file current-source effect scan pass.
- `app/execution_core/protection.py` remains absent from the worktree and current commit. No broker,
  credential, Alpaca, SQL/DDL, database, persistence, runtime-wiring, M2, merge, deletion, or cleanup
  action occurred.

## Claude comparator re-gate

Before the successor freeze, the separately pushed non-authoritative Claude comparator was read via
`git show` without merging its branch. Three gaps still reproduced in the current contract: the
required `Fraction` lifecycle guard was blocked by its `ABCMeta`; Python 3.11 would raise `KeyError`
on version-optional dataclass `slots` metadata; and optional `None` leaves still received a free
wrong-type sentinel mutation. All three are accepted and repaired. The current RED meta controls
also make the already-landed C1/C2/C4 repairs failure-capable over guarded attribute dispatch,
public-entrypoint provenance, real kernel `value` fields, and all nested `ReportedPrice` leaves.
Per-claim authority, reproduction, repair, and deferred Python 3.11 evidence are recorded in
`CLAUDE-COMPARATOR-DISPOSITION.md`. Actual Python 3.11 execution is not claimed locally and remains
an unchanged exact-head CI obligation.

## Post-comparator bounded purity redesign

The successor static gate then received three independent hostile passes. They found five related
P1 classes in the same purity lifecycle: mutable class/function metadata and defaults; callable or
extractor donation across roles; a throwing opaque-factory right-hand side that could expose a
partially initialized value through a traceback; loop/recursion/process-exit paths; and opaque
classes whose decorator shape did not itself prove frozen, slotted, `init=False` construction. Gate
2 therefore triggered one bounded redesign rather than another sequence of edge patches.

The resulting source grammar is closed and production-shaped:

- retained scope admits only inert literals, declarations, and direct imports; `field`, callbacks,
  function defaults, mutable containers, alias/destructuring writes, dynamic module hooks, static
  metadata reads, and callable-as-data paths are refused;
- control flow refuses loops, recursion, suspension, context/exception/match machinery, implicit
  iteration/unpacking/subscription/membership, dynamic calls, and unbounded signatures;
- `_extract_protection_transition` has exactly one direct edge owned by
  `project_protection_venue`; the three public roles cannot delegate to one another;
- both opaque result classes must be exact `@dataclass(frozen=True, slots=True, init=False)` field-
  only declarations, each with one straight-line allocate/write/return factory whose setter inputs
  are already-validated same-named parameters; and
- executable dependency-closure provenance now authenticates every source-reachable private helper
  and every referenced imported binding without executing production.

A final Terra attack found that implicit-iteration builtins and an incomplete no-access sentinel
could hide protocol dispatch. The builtins were removed. The runtime wrong-type matrix now trips
format, truth, ordering, reflected arithmetic, indexing, membership, and iteration protocols before
any payload can execute, while separate lifecycle/value-graph controls seal every admitted exact
type. Focused mutation controls pass, and the same Terra seat returned `ACCEPT` against the complete
two-layer contract with zero P0/P1. This remains pre-freeze evidence only.

## Gate

Production remains barred. Freeze the fully amended immutable RED candidate and require a fresh
independent exact-commit review with zero unresolved P0/P1 before implementing `protection.py`.
