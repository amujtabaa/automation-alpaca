# WO-0148 production successor re-gate

`[FABLE - FULL - verification: DIRECT + independent functional conformance - task: reconcile accepted-RED corrections and complete production pre-flight]`

## Purpose and boundary

This record reconciles the WO-0148 production working copy with the fourteenth RED acceptance.
That acceptance authorized production implementation but depended on unchanged test blobs. During
implementation, several accepted-RED fixtures and oracle expectations proved internally
inconsistent with the normative contract. They were corrected only after a concrete failing
example identified the owning cause. This record therefore supersedes any assumption that the
fourteenth review accepts the changed tests or current production code.

All operational exclusions remain unchanged. The active WO now carries one narrow closeout-only
scope amendment for three status documents, usable only after independent production acceptance;
implementation paths remain unchanged. This re-gate authorizes continued pure validation only. It
does not accept production, close WO-0148, activate WO-0149 or M2, or authorize runtime wiring,
persistence, database activity, credentials, broker activity, merge, deletion, or cleanup.

## Fable gate

```yaml
fable_gate:
  goal: "Reconcile accepted-RED shorthand fixtures/oracles to existing authoritative venue and position semantics, then prove the WO-0148 production successor."
  assumptions:
    - "Venue-owned mandate, active-leg cumulative quantity, canonical basis authority, BUY closure, and admitted source sequence/time remain authoritative."
    - "No production behavior changes merely to satisfy a shorthand test expectation."
  approach: "Map every changed accepted-RED hunk to one normative clause and reproduced counterexample; correct each shared test-owned shorthand class once; retain production defects as separate FIX blocks."
  out_of_scope:
    - "runtime, persistence, database, broker, credentials, M2, WO-0149, merge, deletion, cleanup"
  done_when:
    - "Every post-fourteenth test diff has exact failure/restoration evidence and no weakened invariant."
    - "Focused, static, mutation, predecessor, R2, full-coverage, and scope gates pass at one exact tree."
    - "An immutable candidate receives independent ACCEPT with zero unresolved P0/P1."
  blast_radius: "Allowed pure execution-core source, protection tests, active WO, and REV-0050 records."
```

## Critical pre-flight workflow

1. Re-anchor from `HEAD 486b250`, the active WO, accepted ADR/PKL authority, allowed paths, and the
   preserved untracked evidence inventory.
2. Reconcile every changed fixture and generated-oracle expectation to a reproduced failure and
   one normative clause; retain no unexplained accepted-RED edit.
3. Add focused counterexamples before each production correction. A control must fail for the
   stated reason, not merely because a dependency or type is absent.
4. Correct the owning invariant once, then exercise adjacent branches and sibling histories.
5. Run the complete deterministic/stateful/import focus, Ruff, format, mypy, grammar, scope, and
   exact-diff checks.
6. Execute the work order's named mutation controls with fail/restore evidence.
7. Run predecessor, R2, and full-repository branch-coverage gates.
8. Freeze one immutable candidate only after all local gates pass; submit that exact commit to a
   fresh independent functional-conformance seat and require zero unresolved P0/P1.

Steps 1 through 5 are complete for the current working copy. Steps 6 through 8 remain mandatory.

## Accepted-RED reconciliation

```yaml
fable_fix:
  symptom: "Mandate-isolation and parent-close examples failed after the genuine venue reducer enforced current mandate ownership and active-leg cumulative quantity."
  root_cause: "Two shared fixtures carried a default mandate identity or position aggregate where the contract required the exact effect mandate and active BASE-leg cumulative quantity."
  evidence: "The first complete deterministic production run reported mandate-identity failures; the later generated-history run exposed the BASE-leg cumulative mismatch."
  fix: "Bind custom fixtures to their supplied mandate and derive close cumulative quantity from the active BASE-leg attempt."
  regression_test: "The mandate-isolation examples, parent-close histories, deterministic suite, and both state machines now use exact venue-owned values."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "Formula-loss, trade-window, and configuration-only comparison examples contradicted their own setup."
  root_cause: "The formula case attempted an inadmissible closed-leg revision and an unrestorable metadata transition; the trade pair exceeded its declared window; the configuration comparison also changed execution identity."
  evidence: "The first deterministic production run failed these examples at the genuine venue or evidence boundary."
  fix: "Use an admissible closure-backed revision whose exact upward-tick result has no valid candidate below average, keep the pair at the window boundary, and hold execution identity constant while changing only configuration authority."
  regression_test: "Focused corrected examples and the complete deterministic suite pass; labels now describe rounding unavailability rather than metadata incompatibility."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "Generated histories expected waiting only in exit policies, expected formula authority after a late non-tail correction, and classified a sequence after sequence-less history as non-advancing."
  root_cause: "The test oracle conflated orthogonal BUY-resolution state with goal eligibility, ignored canonical pending-basis state, and applied a sequence comparison without an admitted predecessor sequence."
  evidence: "Successive state-machine runs reduced the failures from the waiting mismatch to the two provenance/precondition mismatches, then to the shared BASE-leg fixture mismatch, before reaching 4/4 pass."
  fix: "Model waiting orthogonally, derive pending-basis formula unavailability, and require an admitted predecessor sequence before applying the non-advance rule."
  regression_test: "Both independent state machines pass all four generated-history tests and replay every input from the same predecessor."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The passive projection graph retained the internal BasisAuthority enum."
  root_cause: "The projection needed only the derived availability fact, not the execution reducer's enum capability."
  evidence: "The passive-value graph control failed on the retained enum type."
  fix: "Retain an exact boolean basis-availability value and continue binding the canonical execution commitment and metadata."
  regression_test: "The passive graph, projection commitment, and formula availability examples pass."
  red_green_verified: true
  attempt: 1
```

No other accepted-RED edit remains unexplained. The changed test blobs require fresh production
acceptance and cannot inherit the fourteenth result by continuity.

## Production pre-flight findings and root corrections

```yaml
fable_fix:
  symptom: "A sibling transition that was correctly stale became applicable when only its proof predecessor cursor was replaced with the already-applied sibling cursor."
  root_cause: "Projection checked current extracted values but did not re-derive the complete predecessor-linked cursor from every retained proof field. The existing top-level field loop changed only the proof's first nested leaf."
  evidence: "A focused counterexample returned STALE for the genuine sibling and APPLIED after predecessor substitution; the new sibling and exhaustive single-leaf controls failed before the repair."
  fix: "The venue now commits predecessor cursor identity, both book scopes and commitments, both execution checkpoints and commitments, summaries, bindings, flags, command, disposition, and delta into a v2 cursor; projection verifies the venue-owned proof commitment and re-derived lineage."
  regression_test: "Every retained proof leaf is changed independently, the proof commitment is recomputed to prevent a seal-only result, and every altered case is rejected. The sibling substitution is rejected specifically by lineage validation."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "When venue economics advanced in the same reducer call as replayed, conflicting, or ineligible optional market input, the new venue state was retained but its disposition or releasable execution goal could be lost."
  root_cause: "Optional market classification returned its standalone outcome after economics had already advanced, instead of preserving the authoritative venue transition and treating unusable market input as an evidence no-op."
  evidence: "Three focused controls failed as EXACT_REPLAY, REFUSED, or APPLIED-without-goal before the correction."
  fix: "When venue state advances, optional market replay/conflict/ineligibility preserves APPLIED, the advanced state, current alert, and any goal now permitted by the advanced projection. Valid market evidence is still reduced against the new economic state."
  regression_test: "Same-call higher-basis economics establishes the new trigger before bids are evaluated; separate replay, changed-payload, and halted cases release the current emergency goal after exact parent closure."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "Three important rejection branches lacked failure-capable controls: invalid TRADE prices, authentic mandate/configuration mismatch, and authentic scope mismatch."
  root_cause: "Existing examples covered equivalent quote and wrong-type paths but not these exact authenticated inputs."
  evidence: "Fresh branch analysis identified the uncovered branches; each new control passes on the current implementation and would fail if its owning comparison were removed."
  fix: "Add zero/misaligned/wrong-tick TRADE histories followed by one valid bid, plus configuration-only and scope-changed projection/mandate compositions."
  regression_test: "Invalid trades cannot supply corroboration; initialization raises on changed authority/scope; reduction refuses an authentic projection produced for changed configuration."
  red_green_verified: true
  attempt: 1
```

 ```yaml
fable_fix:
  symptom: "An authenticated halt did not remain latched for its epoch, and the step limit compared later bids without retaining an eligible intervening trade."
  root_cause: "Halt was classified as an inert occurrence rather than retained stream state, while last-price state was bid-specific instead of primary-occurrence-specific."
  evidence: "Focused counterexamples admitted same-epoch evidence after halt and admitted a large TRADE-to-BID step; both failed before the correction."
  fix: "Commit a stream-halted bit that clears evidence and requires a newer epoch to reopen; retain the last eligible primary price across both BID and TRADE kinds."
  regression_test: "The deterministic halt/reopen and cross-kind step tests pass, both generated histories exercise the rules, and M14/M15 fail when either control is removed."
  red_green_verified: true
  attempt: 1
```

## Failure-capability closure

```yaml
fable_fix:
  symptom: "The first downward-rounding and inclusive-trigger mutants survived their initially selected tests; the overfill mutant failed before reaching the named goal boundary."
  root_cause: "Existing examples used integral pre-tick values, strictly-below-trigger observations, and an earlier overfill policy assertion, so they did not observe the exact mutated decisions."
  evidence: "The initial M01 and M02 commands exited 0 under their mutants. The original overfill node exited 1 at policy classification rather than goal emission."
  fix: "Add a fractional-average rounding example, an exact-trigger equality example, and a dedicated overfill history that reaches the goal assertion."
  regression_test: "Restored production passes all three controls; M01 now yields 92 instead of 93, M02 remains FLOOR_ONLY, and M13 emits a SELL goal with residual 5."
  red_green_verified: true
  attempt: 1
```

All 17 final fail/restore controls, exact commands, decisive failures, restoration method, and final
hashes are recorded in `PRODUCTION-MUTATION-EVIDENCE.md`. M16/M17 use allowed test-local runtime
monkeypatches to remove the live M1C create and final-claim classifiers without editing forbidden
`authority.py`; both make the composition test fail and restore the accepted WO-0147 authority
digest exactly. No predecessor mutation result is overstated or inherited by implication.

## Current evidence

- Complete focused collection: **308 tests** (`287` deterministic, `4` stateful, `17` import
  boundary); all pass on local Python 3.12.13.
- Ruff check: pass. Ruff format check: all seven files already formatted.
- Mypy: success across **86 source files**.
- Import/effect/public-boundary file: **17/17 pass**.
- Python 3.11 grammar parse: **7/7 changed Python files pass**.
- Required fail/restore controls: **17/17 killed and restored**; two initial survivors produced
  three stronger permanent controls before the final pass.
- `git diff --check`: pass.
- Current file blobs, in command order:
  - `protection.py` `ba4303f8d6cc110bf589c1d8061c3ab4d507e7b7`
  - `venue.py` `c80de94968cd6d5a7b651a33a61ec9cff8194e2d`
  - `identity.py` `e5b0fec3035093f38644584ba50621418837563c`
  - `__init__.py` `3012d0ba69063e5a2ee1943d85a4e138cee3229d`
  - `test_protection.py` `ff72af868dca367a4784bef68782d42913c61468`
  - `test_protection_stateful.py` `d30101286d996047d820fdcd19c784e798698e6c`
  - `test_import_boundary.py` `1fd3f78ca360a280de7110d537c1a2545991fb5c`

These are working-copy blobs, not an immutable candidate. Predecessor, R2, full
repository/coverage, final complete-range scope/governance reconciliation, exact commit review,
and Python 3.11/3.12 exact-head CI remain unresolved. No production acceptance is claimed.
