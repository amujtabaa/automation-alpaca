# WO-0148 production pre-flight feasibility re-gate

Status: **READY TO FREEZE - PRODUCTION REMAINS BARRED**

Accepted RED candidate: `0b87a8756d999d81989bb5de1bb895a0ca0d44eb`

Accepted RED evidence head: `e891f42f187cf0965c4057ba5162ca16fe097e44`

Production `app/execution_core/protection.py` is absent. This re-gate changes only the WO-0148 test
contract and its authorized records. It does not authorize runtime or persistence wiring, SQL/DDL,
database initialization, credentials, Alpaca activity, M2, merge, deletion, or cleanup.

`[FABLE - FULL - verification: DIRECT + counterexamples + independent review - task: restore production-contract feasibility]`

## Critical pre-flight result

The pre-flight reproduced two P1 contract contradictions after the twelfth exact RED acceptance:

1. The static grammar required each opaque result to be field-only
   `@dataclass(frozen=True, slots=True, init=False)`. That exact shape permits direct construction
   of an uninitialized slotted value and permits subclass creation, while the runtime contract
   requires both operations to raise `TypeError`.
2. `ExecutionGuard`, `ProtectionMandate`, and `ExecutionGoal` require nonblank text and exact
   32-byte commitments. Their passive runtime lifecycle contract admits `strip` and `len` only
   after exact type guards, but the static call grammar rejected both forms. There is no equally
   clear non-call expression that satisfies the full bytes-length and Unicode-whitespace behavior.

The same findings were independently reproduced by separate read-only Sol and Terra passes.
No production conclusion relies on a database, network, broker, or application-runtime path.

## Root correction

The correction is one bounded source-contract amendment:

- Each opaque result contains declared fields plus exactly two sealed lifecycle methods:
  `__init__(self, *args: object, **kwargs: object) -> None` and
  `__init_subclass__(cls, **kwargs: object) -> None`. Each has one terminal literal
  `raise TypeError(...)`. No other method is admitted. The existing exact write-once factory rule
  remains unchanged.
- The static call checker authenticates only `self.<field>.strip()` immediately after an exact
  `str` guard and `len(self.<field>)` immediately after an exact `str` or `bytes` guard. The pair
  must be in a direct exact dataclass `__post_init__`; the validation is an adjacent top-level
  branch with one terminal literal `ValueError`. Builtins and receiver names must be unshadowed.
- Neither operation is added to a global allowlist. Calls before a guard, against another field or
  receiver, with added arguments, from another method, or through a shadowed name remain refused.

## Step-by-step workflow

1. **Preserve and re-anchor.** Verify the branch, accepted SHAs, active WO, allowed paths, tracked
   diff, retained untracked evidence, clean registered worktrees, and production-module absence.
2. **Prove each contradiction.** Reproduce direct construction and subclassing of the former
   field-only shape. Reproduce rejection of production-shaped guarded `strip` and `len` under the
   accepted static grammar. Record these as feasibility evidence, not production validation.
3. **Repair the owning contract.** Amend the static grammar, the authenticated positive skeleton,
   runtime lifecycle controls, exact public behavior inventory, and the normative WO clause. Keep
   production absent.
4. **Exercise independent counterexamples.** Require separate failures for missing `__init__`,
   missing `__init_subclass__`, malformed lifecycle signature, wrong/extra lifecycle body, extra
   behavior, pre-guard call, wrong guarded type, wrong field, extra arguments, wrong method, and
   shadowed `len`, `type`, `str`, or `bytes`. Confirm the valid minimal shapes pass.
5. **Run focused RED evidence.** Collect and execute the three WO-0148 RED files. Reconcile every
   failure to deliberate production absence or the three required inventory/AST/export deltas;
   no helper or control may fail.
6. **Run preservation and static gates.** Run the 698-test predecessor corpus, Ruff check and
   format-check, Python 3.11 grammar parsing, `git diff --check`, activation-base scope checking,
   accepted-ADR digest checks, current-source effect checks, duplicate-path checks where relevant,
   worktree hygiene, and production-absence verification.
7. **Critical review and freeze.** Perform bottom-up author review plus fresh independent review of
   the current diff. Resolve every evidence-backed P0/P1 at its owning rule. Re-run affected gates,
   create one immutable successor commit, and issue a neutral exact-commit review request.
8. **Resume production only after acceptance.** Production may restart only after a fresh
   independent result reports `ACCEPT`, P0=0/P1=0 at the exact successor. Otherwise keep WO-0148
   active and production barred.

## Current evidence

- Production support edits made before discovery were reverted; the production tracked diff is
  empty and `app/execution_core/protection.py` remains absent.
- Focused collection: **294 tests**.
- Focused execution: **233 expected failures / 61 passes**; the added lifecycle and guarded-call
  controls pass. The 233 failures retain the prior classification: 230 deliberate module-absence
  outcomes plus three required inventory/AST/export deltas.
- Selected lifecycle/static controls: **5/5 passed**.
- Ruff check and Ruff format-check for both changed test files: **passed**.
- Mypy over all 85 application source files: **passed**.
- Current-source effect scan over all eight present execution-core files: **passed**.
- `git diff --check`: **passed**.
- Predecessor corpus: **698/698 passed** in 180.8 seconds.
- Python 3.11 grammar, activation-base scope, accepted-ADR digests, nine auxiliary worktrees, and
  production absence: **passed**. Exact-candidate independent review remains pending.
- Final current-worktree functional-conformance review: **ACCEPT, P0=0/P1=0/P2=0**. This is
  pre-freeze evidence and does not substitute for exact-candidate acceptance.
- Actual Python 3.11 runtime execution remains deferred to unchanged exact-head CI and is not
  claimed locally.

## Continuity checkpoint

After a pause or compaction, resume from this file, the active WO, `git status`, exact HEAD, and the
newest immutable request/result chain. Do not infer completion from the twelfth acceptance because
the later feasibility evidence supersedes its permission to begin production. Keep semantic edits
single-writer and use neutral functional-conformance wording in new records.
