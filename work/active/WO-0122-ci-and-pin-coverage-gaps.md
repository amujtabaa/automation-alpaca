---
type: Work Order
title: "Close CI/pin coverage gaps: run the conformance oracle in CI, pin store lock-liveness, fix a stale fixture"
status: ACTIVE
work_order_id: WO-0122
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
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

- [ ] **C002 (quick win):** make CI collect/run the 61-case conformance oracle — either add an
  explicit `python -m pytest -q tests/r2_conformance_oracle.py` step to `ci.yml`, or `test_`-prefix
  the file so the existing run collects it. The no-collect rationale ("pre-R2") expired at merge
  `88833e3d`. Confirm the oracle runs 61/61 in the CI-form command afterward.
- [ ] **F002:** author failure-capable pins for INV-051 (store lock non-reentrancy) and INV-052
  (off-lock venue IO): a bounded-time dual-store probe that would deadlock/hang if a public method
  re-entered the lock, and a structural/spy check distinguishing local store helpers from
  broker/network awaits under the lock. **Mutation-prove each** (inject a reentrant call / an
  await-under-lock, watch the pin go red, revert, green). Both stores.
- [ ] **C101:** fix or delete the stale inert fixture at
  `tests/test_wo0108_rev0029_remediation.py:268-319` — it latches the recovery on the order being
  claimed (so the block can come from the current-order guard, not the prior-sibling consumer) and
  its comment describes a shape the code doesn't implement. The honest, reason-asserting,
  mutation-proven pin already exists at `tests/test_wo0109_round3_remediation.py:366-393`; align
  or remove the stale one — do not weaken the honest twin.

## Acceptance criteria

- [ ] CI-form command runs the oracle (61/61) alongside the suite; the added step is additive.
- [ ] INV-051/052 pins exist, pass, and are mutation-proven failure-capable on both stores.
- [ ] The stale fixture is fixed/removed with no loss of the honest twin's coverage.
- [ ] `ruff`/`mypy app/`/`lint-imports`/full `pytest` + oracle green; Fable DONE with evidence.

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
