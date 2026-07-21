---
type: Work Order
title: "Close CI/pin coverage gaps: run the conformance oracle in CI, pin store lock-liveness, fix a stale fixture"
status: CLOSED
work_order_id: WO-0122
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen / implementer TBD / from AUDIT-0002 C002 + F002 + C101
created: 2026-07-20
gated_surface: CI workflow (additive only — adds a gate, never loosens one)
---

# Work Order: make the gates actually guard what they claim to

## Goal

Three coverage gaps the audit found: the spec oracle both seats treat as a gate isn't run by CI;
two single-writer-liveness invariants have no failure-capable pin; one stale test fixture pins
the wrong shape. Close all three.

## Context packet

- `work/queue/AUDIT-0002-REMEDIATION-BATCH.md` + `work/review/AUDIT-0002-priorwork/report.md`
  (F002) + `addendum-claude-seat.md` (C002, C101)
- `.github/workflows/ci.yml` (the single pytest invocation) + `tests/r2_conformance_oracle.py`
- `docs/INVARIANTS.md:394-412` (INV-051/052) + both stores' lock discipline
- `tests/test_wo0108_rev0029_remediation.py:268-319` (the stale fixture) and the honest twin
  `tests/test_wo0109_round3_remediation.py:366-393`

## Allowed paths

```yaml
allowed_paths:
  - .github/workflows/ci.yml     # C002: ADD an explicit oracle step (additive)
  - tests/**                     # F002 new pins, C101 fixture fix
  - pkl/architecture/testing-model.md   # note the new lock-liveness pins if apt
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**             # no behavior change; these are guards over existing behavior
  - docs/adr/**
  - .ai-os/**
```

## Required behavior

- [x] **C002 (quick win):** make CI collect/run the 61-case conformance oracle — either add an
  explicit `python -m pytest -q tests/r2_conformance_oracle.py` step to `ci.yml`, or `test_`-prefix
  the file so the existing run collects it. The no-collect rationale ("pre-R2") expired at merge
  `88833e3d`. Confirm the oracle runs 61/61 in the CI-form command afterward.
- [x] **F002:** author failure-capable pins for INV-051 (store lock non-reentrancy) and INV-052
  (off-lock venue IO): a bounded-time dual-store probe that would deadlock/hang if a public method
  re-entered the lock, and a structural/spy check distinguishing local store helpers from
  broker/network awaits under the lock. **Mutation-prove each** (inject a reentrant call / an
  await-under-lock, watch the pin go red, revert, green). Both stores.
- [x] **C101:** fix or delete the stale inert fixture at
  `tests/test_wo0108_rev0029_remediation.py:268-319` — it latches the recovery on the order being
  claimed (so the block can come from the current-order guard, not the prior-sibling consumer) and
  its comment describes a shape the code doesn't implement. The honest, reason-asserting,
  mutation-proven pin already exists at `tests/test_wo0109_round3_remediation.py:366-393`; align
  or remove the stale one — do not weaken the honest twin.

## Acceptance criteria

- [x] CI-form command runs the oracle (61/61) alongside the suite; the added step is additive.
- [x] INV-051/052 pins exist, pass, and are mutation-proven failure-capable on both stores.
- [x] The stale fixture is fixed/removed with no loss of the honest twin's coverage.
- [x] `ruff`/`mypy app/`/`lint-imports`/full `pytest` + oracle green; Fable DONE with evidence.

## Stop conditions

Stop if pinning INV-051/052 surfaces an ACTUAL reentrancy or off-lock-IO defect in current code
(that would be a real P0/P1 → escalate immediately, do not paper over with a passing test).
Rollback: revert; tests/CI-config only.

## Notes

C002 is the cheapest high-value item in the whole batch — a live gate the whole team believes is
running actually isn't. Prioritize it even if F002/C101 slip to a follow-up.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.

## Fable gate

```yaml
fable_gate:
  goal: "Make CI run the R2 conformance oracle, add failure-capable INV-051/052 lock-liveness pins, and repair the stale WO-0108 recovery fixture."
  assumptions:
    - "Current store code has no actual reentrant lock acquisition or await-under-lock defect; any contrary evidence is an immediate P0/P1 stop."
    - "Temporary mutation probes may touch app/store files only in the working tree and must be reverted with apply_patch before any commit."
    - "The CI change is additive and does not alter or weaken the existing full-suite coverage gate."
  approach: "Add red CI-presence coverage, author bounded dual-store and structural pins, mutation-prove each store/property, align the stale fixture to the prior-sibling shape, then add the explicit oracle step and testing-model note."
  out_of_scope:
    - "permanent app/** changes"
    - "docs/adr/**"
    - ".ai-os/**"
    - "any weakening or deletion of the honest WO-0109 sibling pin"
  done_when:
    - "CI-form oracle command reports 61/61 and workflow coverage proves the step is additive."
    - "INV-051/052 pins pass and turn red under deliberate mutations for both stores."
    - "The stale fixture asserts a distinct prior-sibling recovery and the honest twin remains green."
    - "Full gates, close-out, disposition, ledger, move, and scoreboard are complete."
  blast_radius: ".github/workflows/ci.yml, tests/**, testing-model PKL, and work records"
```

## Fable fixes

```yaml
fable_fixes:
  - symptom: "The 61-case R2 conformance oracle passed locally but was never collected by the repository's CI workflow."
    root_cause: "The oracle retained a non-test filename from its pre-R2 incubation period, and CI had no explicit invocation after R2 merged."
    evidence: "The red workflow-presence test failed because ci.yml contained no tests/r2_conformance_oracle.py command."
    fix: "Add a dedicated oracle invocation before the unchanged full coverage run and pin both steps structurally."
    regression_test: "tests/test_ci_lock_liveness_pins.py::test_ci_runs_r2_oracle_additively"
    red_green_verified: true
    attempt: 1
  - symptom: "INV-051 and INV-052 were prose invariants without executable failure-capable guards for either store."
    root_cause: "Existing store tests exercised successful operations but did not bound public-method re-entry or inspect awaits nested under the single-writer lock."
    evidence: "Temporary reentrant mutations timed out for memory and sqlite; temporary await-under-lock mutations failed the AST guard for each store."
    fix: "Add a bounded dual-store flatten probe and an AST lock-region pin that permits local awaits but rejects any await under the store lock."
    regression_test: "tests/test_ci_lock_liveness_pins.py"
    red_green_verified: true
    attempt: 1
  - symptom: "The first repaired WO-0108 fixture still failed to establish an unambiguous terminal prior sibling."
    root_cause: "The distinct prior order was canceled before it entered SUBMITTED with a broker identity, so the recovery consumer could still classify the obligation as ambiguous."
    evidence: "The focused test failed after the first alignment attempt; the honest twin exposed the missing SUBMITTED-with-broker-id transition."
    fix: "Mirror the honest sibling shape: transition O1 through SUBMITTED with its broker id, then CANCELED, and assert O2 is blocked specifically by O1."
    regression_test: "tests/test_wo0108_rev0029_remediation.py::test_lane_a_claim_blocks_recovery_latched_after_stage"
    red_green_verified: true
    attempt: 2
```

## Fresh evidence

```yaml
evidence:
  - command: "CI-presence regression before and after .github/workflows/ci.yml edit"
    result: PASS
    decisive_output: "Red before because no explicit oracle command existed; green after with the original full coverage step retained."
  - command: "temporary INV-051/052 mutations in app/store/memory.py and app/store/sqlite.py"
    result: PASS
    decisive_output: "Both reentrant-call mutations timed out red; both await-under-lock mutations failed red and named the mutated store; all temporary app changes reverted."
  - command: "pytest -q tests/r2_conformance_oracle.py with OS-temp basetemp"
    result: PASS
    decisive_output: "61 passed in 5.34s."
  - command: "focused CI/pin and stale-fixture regressions"
    result: PASS
    decisive_output: "9 passed; the honest WO-0109 twin remained green."
  - command: "ruff check .; mypy app/; lint-imports"
    result: PASS
    decisive_output: "All ruff checks passed; mypy succeeded on 64 files; all 6 import contracts kept."
  - command: "full pytest with addopts cleared, cache provider disabled, and unique OS-temp basetemp"
    result: PASS
    decisive_output: "3867 passed, 11 skipped, 1 xfailed in 366.60s."
  - command: "five AI-OS checks; work-order scope; context hygiene"
    result: PASS
    decisive_output: "Install, version, ledger, PKL, disposition, scope, and hygiene gates passed on the close-out tree."
```

The repository-wide format check identified one pre-existing unrelated file,
`work/review/AUDIT-0002-priorwork/probe_review_integrity.py`, that would be reformatted. It is
outside this work order's allowed edits and was left untouched. Both changed Python test files
were independently verified formatted.

The first static command resolved the system Python 3.14 interpreter, which does not contain
`ruff`. Root cause was interpreter selection, not repository behavior; the authoritative static
rerun used the repository's pinned `.venv` tools and passed.

## Fable done

```yaml
fable_done:
  task: "WO-0122 CI oracle, lock-liveness pins, and stale recovery fixture"
  done_when_results:
    - item: "CI invokes the 61-case R2 conformance oracle explicitly and retains its existing full-suite coverage gate."
      status: MET
    - item: "INV-051 non-reentrancy and INV-052 off-lock await pins cover both stores and turn red under deliberate mutations."
      status: MET
    - item: "The WO-0108 fixture now uses a distinct terminal prior sibling and preserves the honest WO-0109 twin."
      status: MET
    - item: "Static gates, oracle, full suite, five AI-OS checks, scope, and hygiene are green with fresh evidence."
      status: MET
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    permanent_app_changes: false
  evidence:
    - "61 passed in the explicit conformance oracle"
    - "3867 passed, 11 skipped, 1 expected xfailed in the full suite"
    - "Mutation red/green evidence for both invariants and both stores"
    - "Five AI-OS checks, scope, and hygiene passed"
  status: VERIFIED
```
