# WO-0148 RED contract correction workflow

Status: **COMPLETE — TWELFTH EXACT RED CONTRACT ACCEPTED**

Exact starting candidate: `5c5bee9543b78fc2fa8f612c61d75d4fdbf52bae`

Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

Production `app/execution_core/protection.py` is absent and remains prohibited until a later exact
candidate receives fresh independent acceptance with zero unresolved P0/P1.

`[FABLE • FULL • verification: DIRECT + independent review • task: restore RED-contract feasibility]`

## Diagnosed contradiction

The frozen contract requires the non-private runtime names in `protection.py` to equal its exact
`__all__`. It also requires imports such as `dataclass` and `Enum`, while the static grammar rejects
all renamed imports. An ordinary import therefore creates an extra public runtime name, and the two
requirements cannot be satisfied together.

The public-surface requirement remains unchanged. The correction makes implementation dependencies
private through one exact import spelling rule.

```yaml
fable_gate:
  goal: "Restore a feasible, exact protection import contract without weakening the public surface."
  assumptions:
    - claim: "An unaliased future-annotations directive does not create an ordinary runtime module binding."
      status: REFUTED
      evidence: "The failure-first executable sample retained a public annotations binding; the canonical _annotations form preserves future behavior and keeps the dependency private."
    - claim: "An imported name beginning with an underscore is already private."
      status: VERIFIED_BY_SYNTAX
    - claim: "Every other approved imported dependency can be referenced through its canonical underscore-prefixed local name."
      status: VERIFIED_BY_CONTROLS
      evidence: "The authenticated checker sample, executable public-surface sample, imported-annotation resolver, and altered-source controls all pass."
  approach: "Prove the contradiction with a failing control, apply one canonical import rule, verify feasible construction and rejected alternatives, complete critical pre-flight, then freeze and request independent review."
  out_of_scope:
    - "production protection implementation"
    - "runtime or persistence wiring"
    - "database, broker, credential, or Alpaca activity"
    - "M2, merge, deletion, or cleanup"
  done_when:
    - "canonical private imports satisfy the complete static grammar"
    - "ordinary public imports and noncanonical aliases are rejected"
    - "already-private dependencies remain unaliased"
    - "imported type annotations use their retained canonical private names"
    - "runtime replacement-type resolution recognizes the canonical private annotation strings"
    - "the executable feasibility control has an exact public surface"
    - "focused RED and predecessor classifications reconcile"
    - "all static, scope, provenance, and production-absence gates pass"
    - "fresh independent exact-commit review reports zero unresolved P0/P1"
  blast_radius: "tests/execution_core/test_import_boundary.py, tests/execution_core/test_protection.py, WO-0148, and REV-0050 records"
```

## Step-by-step execution

### 1. Preserve and re-anchor

1. Preserve the tenth candidate, its request, all earlier reviewer-owned results, and unrelated
   retained evidence unchanged.
2. Confirm the tracked tree, candidate SHA, branch relationship, active WO, allowed paths, accepted
   authority digests, and production-module absence.
3. Record any platform interruption as an interruption, never as a review verdict.

### 2. Establish failure-first evidence

1. Add an executable source sample using canonical private imports:
   `dataclass as _dataclass`, `Enum as _Enum`, and a representative public execution-core type as
   its exact underscore-prefixed local name.
2. Require the current static grammar to accept that sample. Run this one control before changing
   the checker and record its expected failure.
3. Execute a small test-only module sample and require its non-private runtime names to equal its
   declared `__all__`, including confirmation that future annotations uses the canonical private
   binding.
4. Add altered-source controls for an unaliased public import, an arbitrary alias, a wrong private
   alias, a second-leading-underscore alias, a renamed or redundantly aliased already-private
   dependency, an unaliased future import, a module import, a wildcard import, a duplicate binding,
   post-import rebinding, an unprefixed imported annotation, and an explicitly quoted annotation.
   Each must be rejected for the intended rule-specific reason.

### 3. Apply the root correction

1. Require `from __future__ import annotations as _annotations`; the directive remains active while
   its runtime binding stays private.
2. Keep approved imported names that already begin with `_` unaliased.
3. Require every other approved `ImportFrom` dependency to use exactly `Name as _Name`.
4. Continue rejecting module imports, nested or conditional imports, wildcard imports, duplicate
   bindings, arbitrary aliases, rebinding, and unapproved canonical sources.
5. Update the exact opaque dataclass spelling and authenticated construction sample to the canonical
   private names. Preserve canonical source-identity resolution and every existing call, enum,
   extractor, write, and public-role restriction.
6. Require imported type annotations to use their retained private names. In particular, the public
   venue entrypoint exposes the runtime string `_VenueRecoveryTransition`, and optional-field
   replacement resolution recognizes `_ReportedPrice`, `_Decimal`, and `_Fraction` without
   accepting the corresponding public imported names.
7. Restrict annotation expressions to loaded names, PEP 604 unions, `None`, exact
   `frozenset[...]` and `type[...]` forms, fixed multi-element tuples, and homogeneous
   `tuple[T, ...]`. Reject one-element tuple annotations in both `tuple[T]` and `tuple[T,]`
   spellings, and permit `...` only as the second element of a two-item homogeneous tuple
   annotation. Reject explicit string constants so deferred runtime metadata remains tied to the
   inspected names rather than gaining another quoting layer.
8. Exercise every accepted annotation branch in one static positive sample and directly reject a
   one-element tuple plus a malformed tuple with an extra element before `...`.
9. Update production-shaped altered-source samples where necessary so each continues to test its
   named rule rather than failing earlier for import spelling.

### 4. Critical pre-flight

The pre-flight is a functional-conformance review, not independent acceptance.

1. Re-read every changed function in full context and trace each changed line to this contradiction.
2. Check the rule table exhaustively: future import, public standard-library import, public internal
   import, already-private internal import, arbitrary alias, module import, wildcard import,
   duplicate binding, rebinding, imported annotation provenance, and exact annotation-expression
   grammar.
3. Show that the positive construction sample has no non-private imported dependency and retains an
   exact `__all__`.
4. Show that every altered-source control fails before restoration and the restored control passes.
5. Confirm that canonical origin checks, source/runtime provenance checks, exact enum resolution,
   opaque factory checks, and the single venue-extractor edge remain intact.
6. Run focused collection and RED classification. Every failure must still be attributable only to
   deliberate production absence or the three required inventory/export deltas.
7. Run the complete predecessor execution-core corpus with the three RED files excluded.
8. Run Ruff check and format check, Python 3.11 grammar parsing, diff check, activation-base scope
   check, accepted-ADR digest checks, current-source effect checks, duplicate-path checks where
   applicable, and production-absence verification.
9. Perform a bottom-up self-review and a fresh read-only review. Resolve every evidence-backed P0/P1
   at its owning rule and rerun all affected gates.

### 5. Freeze and independently review

1. Reconcile the workflow, active WO, tenth disposition, and new evidence without modifying any
   preserved reviewer result.
2. Commit only allowed paths as one bounded successor RED candidate.
3. Create a new exact-commit review request using neutral functional-conformance language.
4. The independent seat writes findings only to a new result file and reports exact P0/P1 counts.
5. Production remains prohibited unless the exact successor receives `ACCEPT` with zero unresolved
   P0/P1. A platform interruption or incomplete review is not acceptance.

## Reconciled evidence

- Complete focus: **292 collected / 233 expected RED failures / 59 passes**.
- Correctly excluded predecessor corpus: **698/698 passed** in 157.08 seconds. The sole warning was
  the pre-existing inability to write `.pytest_cache`; test collection and execution were
  unaffected.
- Canonical import, exact public-surface, private annotation resolution, annotation-expression,
  and altered-source controls pass.
- Ruff check/format-check, Python 3.11 grammar parsing for both changed Python files,
  `git diff --check`, activation-base scope, accepted ADR digests, eight-file current-source effect
  scan, and production absence pass.
- All nine auxiliary registered worktrees are clean. Successor candidate paths reconcile against
  WO-0148's allowed paths; the preserved untracked tenth request and unrelated retained evidence
  remain outside each candidate commit.
- Final critical current-worktree pre-flight verdict: **ACCEPT, P0=0, P1=0**. This does not replace
  the required fresh independent exact-commit verdict.

## Eleventh exact-review correction

Independent review of exact commit `8d441d6bbbf90c634e073337ea28b2a758070bc4` returned
`BLOCK`, P0=0/P1=1. The accepted one-element `tuple[T]` branch had neither a production requirement
nor a direct control, and removing only that branch left the owning positive controls green.

The successor narrows the grammar instead of adding unused capability: both `tuple[T]` and its
trailing-comma-equivalent `tuple[T,]` are refused. Direct altered-source controls fail before each
owning grammar correction and pass afterward. The complete focus remains **292 collected / 233
expected RED failures / 59 passes**. Production remains absent. The eleventh result is preserved
unchanged, and a new immutable successor requires a fresh independent exact-commit verdict.

Final post-eleventh current-worktree pre-flight is **ACCEPT, P0=0/P1=0/P2=0**. A live expression
matrix passes 6 accepted and 8 refused forms, and independent in-memory restorations prove both
one-item tuple controls can fail. This is re-freeze evidence only.

## Twelfth exact acceptance

Fresh independent review of exact commit `0b87a8756d999d81989bb5de1bb895a0ca0d44eb` returned
**ACCEPT, P0=0/P1=0**. The review independently reproduced the 292-test focused classification,
698/698 predecessor preservation, 6/6 accepted and 8/8 refused annotation matrix, both independent
tuple-control restorations, all static/scope/digest/effect/worktree gates, and production absence.

The corrected RED contract is accepted only for permission to begin WO-0148 production
implementation. Actual Python 3.11 execution remains an unchanged exact-head CI obligation.
Production behavior, implementation review, WO closeout, and later slices remain separate gates.

## Continuity checkpoint

After compaction or pause, resume from this file, the active WO, `git status`, the exact HEAD, and
the newest immutable request/result/disposition chain. Do not infer state from conversation text.
Keep semantic edits single-writer; parallel work is limited to read-only analysis and independent
review. Use only functional-conformance, feasibility, contradiction, and negative-control
terminology in new review material.
