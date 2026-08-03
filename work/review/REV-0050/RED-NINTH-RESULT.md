# WO-0148 ninth RED exact-commit independent review

Exact candidate reviewed: `706ed536790179fcb673aaedf96b3b728ee33d3c`
Activation base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## P1 findings

### P1-1 — Restart replay exactness is pinned for only one of four occurrence forms

**Location:** `tests/execution_core/test_protection.py:6830`

**Authority:** ADR-021 at `docs/adr/ADR-021-position-protection-liquidity-execution.md:125`
requires an exact source-occurrence replay after restart to be an evidence no-op. WO-0148 clause 11
at `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:119` requires the same
for replay/restart delivery. The accepted eighth-review disposition additionally requires
`EXACT_REPLAY`, unchanged complete state/commitment, no goal/alert, and an advancing successor whose
evaluation time lies between the original and replay-delivery contexts.

**Concrete disproof:** The sole changed-delivery-context replay at lines 6836-6882 uses the helper
defaults `kind="BEST_BID"` and `sequence=7`. The other duplicate controls replay either the exact
same object (`tests/execution_core/test_protection.py:7095` and
`tests/execution_core/test_protection_stateful.py:628`) or venue transitions rather than market
occurrences. A reducer mutant can therefore implement the repaired behavior only for sequenced
`BEST_BID`, while treating the same adapter-stable `TRADE` occurrence, or either market kind with
`source_sequence=None`, as new evidence or equivocation when only evaluation context changes. It
still passes the existing exact-object duplicate tests and the changed-payload equivocation matrix.
For the uncovered advancing case, the replay can retain evaluation time 109 and suppress an
otherwise-valid distinct successor at evaluation time 107, recreating the negative evidence
authority that the ninth re-gate is intended to kill.

**What resolves it:** Make the changed-delivery replay a failure-capable matrix over both
`MarketKind` values and present/absent source sequence. Each cell must require `EXACT_REPLAY`, a
pre-call snapshot of every retained state field and commitment to remain unchanged, no goal/alert,
and acceptance of a distinct successor whose evaluation time is between the original and replay
delivery contexts. Add the changed-context replay to the generated market history as a further
generalization control.

### P1-2 — Match capture launders runtime output through an approved import

**Location:** `tests/execution_core/test_import_boundary.py:634`

**Authority:** ADR-020 at `docs/adr/ADR-020-current-state-execution-kernel.md:30` prohibits I/O and
logging in the pure reducer. WO-0148's RED boundary at
`work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:201` requires the import/
public-surface pins to fail if protection gains I/O. The accepted eighth-review repair claims a
complete call/import/binding-provenance model rather than relying on runtime capture alone.

**Concrete disproof:** The `rebound` inventory at lines 634-641 sees `ast.Name(Store|Del)` and
arguments, but Python pattern-capture targets live as strings in `ast.MatchAs`, `ast.MatchStar`, and
`ast.MatchMapping`, so they are never marked rebound. A synthetic protection source imported the
approved `dataclasses.dataclass` as `_dataclass`, captured its bound `__getattribute__` into a
declared `_getter`, used split string constants to recover its globals, captured builtin `print`
into a declared `_emit`, and called `_emit` only when `source_sequence == 424242`. Both
`_effect_call_violations(...)` and `_protection_call_binding_violations(...)` returned `[]`; executing
the sentinel branch printed `transitive output escaped`. The rule at lines 819-829 permits
`object.__getattribute__(..., "__getattribute__")`, and the final call looks like an approved local
declaration because the pattern rebind is invisible. The current no-output runtime test exercises
only `None` and one ordinary occurrence, so it does not catch the hidden branch. The committed
positive skeleton and existing structural mutant test still pass, demonstrating that their green
result does not close this transitive donation path.

**What resolves it:** Use one exhaustive Python binding collector for imports, assignments,
arguments, exception targets, and every pattern-capture form, and reject calls through any name
with more than one possible binding. Narrow `object.__getattribute__` to exact approved passive
field reads on proven receiver types; acquiring `__getattribute__`/`__setattr__` or other callable
metadata must fail. Add this exact match-capture/output mutant while retaining the positive
production-shaped skeleton.

### P1-3 — The purity model does not model write effects or persistent hidden state

**Location:** `tests/execution_core/test_import_boundary.py:158`

**Authority:** ADR-020 defines one pure transition reducer at
`docs/adr/ADR-020-current-state-execution-kernel.md:24` and prohibits runtime effects at line 30.
WO-0148 declares the slice pure and deterministic at
`work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:31`. The generated-suite
contract also claims input immutability at `tests/execution_core/test_protection_stateful.py:5`.

**Concrete disproof:** The scanner recognizes selected effectful calls but not state writes.
Synthetic protection mutants for all of the following returned no violation from either static
oracle: module-global list subscript `AugAssign`; `global _count` plus integer `AugAssign`; a private
helper with a persistent mutable default; and direct
`object.__setattr__(state, "value", object.__getattribute__(state, "value"))`. The last capability is
explicitly allowlisted at line 158, while lines 759-762 reject only attribute assignment syntax,
not writes performed by that call or by subscript/global/nonlocal forms. Calling the global-list
mutant twice returned the identical output object both times while its retained audit state advanced
to `[2]`. Thus a future otherwise-correct reducer can mutate persistent module/default/closure state
or caller-owned immutable inputs and still pass the static gate, stdout/stderr capture, and
same-output replay checks. In particular, `_reduce` at lines 548-552 retains aliases to its inputs,
so its post-call tuple equality is not an independent snapshot against in-place mutation.

**What resolves it:** Add a protection-specific write-effect/provenance grammar that rejects
`global`/`nonlocal` mutation, writes through attributes or subscripts into module/import/input-
reachable objects, persistent mutable defaults/closures, and unrestricted direct object setters.
If opaque construction needs `object.__setattr__`, allow it only on a proven fresh local instance,
inside its bounded construction path, before escape. Add failure-capable mutants for module
subscript state, global rebinding, retained default/closure state, and input mutation; retain a
positive construction/reducer skeleton to prove feasibility.

## Evidence reconciliation

- `HEAD` is the requested `706ed536790179fcb673aaedf96b3b728ee33d3c`; the activation base is an
  ancestor. Before this result was written, the result path did not exist and there were no tracked
  or staged changes. The activation-base diff has nine allowed-path files, no deletion, no
  production module, and no broker/runtime/persistence surface.
- Complete focused collection reproduced 284 tests: 266 deterministic protection, four stateful,
  and 14 import-boundary tests.
- Exact RED execution reproduced `228 failed, 56 passed`: 221/45 in `test_protection.py`, 3/1 in
  `test_protection_stateful.py`, and 4/10 in `test_import_boundary.py`. The first 225 failures are
  caused by deliberate protection-module absence; the remaining three are the required module-
  inventory, AST/import, and package-export deltas. No oracle helper failed.
- Eight selected provenance, no-access, lifecycle, exhaustive-leaf, bounded-map, stateful-
  registration, and effect-model meta-controls passed. The committed structural capability mutant
  test and positive skeleton also passed, but the additional match-capture and write-effect mutants
  above survived both owning static oracles.
- The unchanged predecessor execution-core corpus collected and passed 698/698 tests in 187.41
  seconds with all three deliberate RED files excluded.
- Ruff check and format-check, Python 3.11 grammar parsing of all three RED files, `git diff
  --check`, the activation-base scope checker, production absence in both worktree and target tree,
  and all three accepted ADR digests passed. The eight currently present execution-core source
  files reported zero violations under the committed effect scanner.
- After this artifact was written, tracked and staged diffs remained empty. Relative to the
  preserved pre-review status, `RED-NINTH-RESULT.md` is the only added path; the untracked ninth
  request and retained coverage/XML evidence pre-existed and remain untouched.

## Unverified items

- No Python 3.11 interpreter is installed locally. Only its grammar target was checked; actual
  Python 3.11 execution remains an exact-head CI obligation.
- Production `app/execution_core/protection.py` is deliberately absent. Domain behavior and the
  required implementation mutation-kill/restoration evidence cannot yet be executed.
- Network/CI state, broker behavior, credentials, SQL/DDL, database/persistence behavior, runtime
  wiring, and repository-wide tests outside the 698-test predecessor corpus were not exercised,
  consistent with the RED review boundary.

## Verdict

**BLOCK**

P0: **0**
P1: **3**

Three unresolved P1 test-contract gaps remain. Production implementation must remain barred until
they are repaired at their owning replay/binding/effect boundaries, affected evidence is rerun, and
a fresh immutable RED candidate receives independent zero-P0/P1 acceptance. This verdict governs
only permission to begin WO-0148 production implementation; it does not close the work order or
replace the later implementation review.
