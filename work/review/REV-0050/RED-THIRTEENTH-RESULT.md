# WO-0148 thirteenth exact-commit functional-conformance review

Exact candidate reviewed: `0a36656388703c526b1d1e5eb9cb52d0147a1d43`

Reviewed predecessor: `e891f42f187cf0965c4057ba5162ca16fe097e44`

Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

## Findings

### P1 - Historical work-order rewrites exceed the bounded feasibility correction

- **Location:** `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:44`
  (also lines 62, 213, 264, 312, 390, 417, 449, 491, 501-509, 597, 612, 640-641, 682,
  710, 726, 734-735, and 787)
- **Requirement:** `AGENTS.md:66` classifies any changed line that does not trace to the stated
  decision as P1 scope creep. The controlling re-gate defines one bounded source-contract amendment
  at `work/review/REV-0050/PRODUCTION-PREFLIGHT-FEASIBILITY-REGATE.md:31-49` and limits neutral
  functional-conformance wording to **new records** at line 101. The thirteenth request objective 7
  separately requires every change to trace to the executable contract without unrelated behavior
  or authority.
- **Evidence (`reproduced-live`):** `git diff --unified=0 e891f42f..0a366563 --
  work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md` reports 21 hunks. The
  final two are the authorized guarded-call/opaque-lifecycle amendment and current re-gate record;
  the preceding 19 rewrite already-existing goal, Fable, mutation, and prior-review history. A
  word-level diff shows, for example, `independently refute ... kill named mutants` changed to
  `independently check ... exercise named counterexamples` at line 62, `bypass M1C ... gates`
  changed to `omit M1C ... gates` at line 213, and repeated historical `hostile`, `attack`, or
  `bypass` descriptions replaced throughout lines 264-787. Repository search found no authority to
  normalize existing WO history; the only applicable instruction says to use neutral wording in new
  records. The path-based scope checker still reports `SCOPE CHECK PASSED`, demonstrating that it
  cannot detect this line-level excess.
- **Impact:** The candidate rewrites retained campaign history outside the two diagnosed
  contradictions and changes precise mutation/bypass language in the active authority record. That
  weakens traceability from the exact candidate to its stated decision and makes later seats
  distinguish editorial reinterpretation from the actual lifecycle/guarded-call correction. Under
  the repository's explicit rubric, an allowed path does not make unrelated changed lines
  acceptable.
- **Resolution:** Revert the 19 preexisting-history wording hunks. Retain the bounded normative
  amendment beginning at current line 803 and the production pre-flight re-gate section beginning at
  current line 913, then freeze a successor and rerun the affected diff/scope/static gates.

## Evidence reconciliation

- **Target and committed scope (`reproduced-live`):** `HEAD` remained the exact requested candidate;
  its sole parent is the requested predecessor, and the activation base is an ancestor. The direct
  candidate changes five WO-0148-allowed paths and contains no deletion, production module,
  runtime/persistence/broker surface, SQL/DDL, or database change. The activation-base mechanical
  scope checker passed.
- **Feasibility contradictions (`reproduced-live`):** an independent local Python example of the
  former field-only `@dataclass(frozen=True, slots=True, init=False)` shape constructed an instance
  with its field absent and admitted a subclass. The corrected local lifecycle probe rejected both
  direct construction and subclass creation with `TypeError`.
- **Source contract (`reproduced-live`):** the authenticated positive skeleton passed with both
  opaque types, their exact `__init__`/`__init_subclass__` seals, one write-once factory per type,
  and exact guarded `strip`/`len` validation. Independent in-memory probes confirmed guarded
  `len(self.<str-field>)` is admitted, a wrong `strip` receiver is refused, and reversed opaque
  lifecycle order is refused. The source exception remains local to exact adjacent dataclass
  `__post_init__` validation rather than becoming a global `len` or `strip` allowance.
- **Failure-capable controls (`reproduced-live`):** the committed negative matrices report their
  rule-specific violations for missing seals, malformed signatures/annotations/bodies, extra
  behavior, pre-guard ordering, wrong guarded type/field/size, added arguments, wrong method, and
  shadowed `len`, `type`, `str`, and `bytes`. Five isolated lifecycle/static controls passed 5/5.
- **Focused RED classification (`reproduced-live`):** collection reported 273 deterministic
  protection tests, four stateful tests, and 17 import-boundary tests: 294 total. Exact execution
  produced 233 expected failures and 61 passes. The import-boundary failures separate into one
  explicit missing-semantic-center assertion and the three required inventory, AST/import, and
  package-export deltas; the other 229 failures are direct missing-production-module outcomes. No
  helper or meta-control failed.
- **Predecessor preservation (`reproduced-live`):** the 11 execution-core predecessor files,
  excluding the three failure-first RED files, collected and passed 698/698 tests in 178.1 seconds.
- **Static and authority gates (`reproduced-live`):** Ruff check and Ruff format-check passed for all
  three RED files; all three parsed under the Python 3.11 grammar target; mypy passed over all 85
  application files; `git diff --check` passed for both reviewed ranges; all three accepted ADR
  SHA-256 values matched the ratification index; and the eight currently present execution-core
  source files produced zero findings under the committed effect scanner.
- **Preservation (`reproduced-live`):** all nine registered auxiliary worktrees were clean when
  checked with one-shot safe-directory configuration. Production `app/execution_core/protection.py`
  is absent from both the worktree and exact target. Before this result was written, tracked and
  staged diffs were empty and the retained untracked evidence/request paths matched the initial
  review status. No credentials, network/broker call, SQL/DDL, database initialization,
  persistence/runtime change, merge, deletion, cleanup, commit, or push occurred.

## Unverified items

- No local Python 3.11 interpreter is available. Python 3.11 grammar parsing was reproduced; actual
  Python 3.11 execution remains an unchanged exact-head CI obligation.
- Production `app/execution_core/protection.py` is deliberately absent. Production functional
  conformance and implementation mutation-restoration evidence cannot yet be executed.
- Network/CI state, broker behavior, credentials, SQL/DDL, database/persistence behavior, runtime
  wiring, and repository tests outside the 698-test pure predecessor corpus were not exercised, in
  accordance with this review boundary.

## Verdict

**ACCEPT-WITH-CHANGES**

P0: **0**

P1: **1**

P2: **0**

The lifecycle and guarded-call RED correction is functionally supported, but the unrelated
work-order-history rewrites must be removed before WO-0148 production implementation resumes. This
verdict governs only permission to resume WO-0148 production implementation; it neither accepts
production nor closes the work order.
