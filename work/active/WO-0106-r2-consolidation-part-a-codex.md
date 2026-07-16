---
type: Work Order
title: R2 consolidation investigation and decision package (Codex seat)
status: ACTIVE
work_order_id: WO-0106
wave: W3
model_tier: strong
risk: high
disposition: []
owner: Codex
created: 2026-07-16
---

# Work Order: R2 consolidation investigation and decision package (Codex seat)

## Goal

Execute Part A of `CONSOLIDATION-CHARTER.md` independently, producing a spec-derived
R2 conformance oracle and a decision-ready consolidation report, then stop for the
human's recorded ratification before any Part B implementation.

## Context packet

Read only these first, expanding only where the charter requires direct evidence:

- `AGENTS.md`
- `CLAUDE.md`
- `CONSOLIDATION-CHARTER.md`
- `.ai-os/templates/fable-core-v3.md`
- `docs/adr/ADR-010-execution-envelope.md`
- `docs/INVARIANTS.md`
- `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`
- `work/active/WO-0036-*` or the corresponding WO-0036 variant on each compared tip
- `work/active/W3-STATE.md`
- the AUDIT-0001 / treadmill charter identified from those sources
- the R2 implementation and test files named by the charter on each compared tip

## Allowed paths

```yaml
allowed_paths:
  - app/store/base.py
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/monitoring.py
  - app/reconciliation.py
  - tests/**
  - docs/adr/ADR-010-execution-envelope.md
  - docs/INVARIANTS.md
  - docs/SPINE_EXECUTION_ARCHITECTURE_v2.md
  - pkl/**
  - work/active/W3-STATE.md
  - work/active/WO-0036-*
  - work/queue/WO-0036-*
  - work/queue/WO-0106-r2-consolidation-part-a-codex.md
  - work/active/WO-0106-r2-consolidation-part-a-codex.md
  - work/completed/WO-0106-r2-consolidation-part-a-codex.md
  - work/ledger.jsonl
  - work/review/CONSOLIDATION-R2-PARTA-CODEX/**
```

Any Part B path not listed here requires a ratified work-order update before use.

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - streamlit_app/**
  - .github/workflows/**
  - data/**
  - migrations/**
```

No live/shadow-mode activation, broker submission, schema migration, PR mutation,
shared-branch rewrite, or Part B implementation is authorized by this work order.

## Required behavior

- [ ] Verify the complete topology, inventory, freeze set, live PR state, and all relevant identifiers across Git and GitHub.
- [ ] Derive an implementation-independent conformance oracle from the accepted spec sources and run it against both R2 attempts.
- [ ] Characterize both mechanisms symmetrically and discharge correctness, parity, migration, governance, and no-second-stored-truth obligations.
- [ ] Measure both mechanisms under an explicit monitoring-tick latency budget.
- [ ] Cross-run each attempt's adversarial suites against the other and adjudicate every divergence against the spec.
- [ ] Produce the Sections A-I decision package and a command-backed Section J evidence appendix.
- [ ] Commit only the Codex Part A report and oracle artifacts after this work order, surface Section I to the human, and stop before Part B.

## Required tests

- [ ] Property/regression: `tests/test_r2_conformance_oracle.py` exercises both stores and every treadmill sibling named in the charter.
- [ ] Differential: the same oracle runs on both live R2 implementation tips in isolated scratch worktrees.
- [ ] Cross-verification: Sol hostile/assurance/performance suites run against Claude, and Claude fresh-eyes/masked-predecessor pins run against Sol with only recorded fixture adaptation.
- [ ] Parity: memory and SQLite emit equivalent observable R2 behavior, including restart/startup projection where applicable.
- [ ] Performance: both designs are measured over increasing event-log sizes against a stated tick budget.

## Required commands

```bash
ruff check .
ruff format --check .
mypy app/
lint-imports
pytest -q
pytest --cov=app --cov-branch --cov-fail-under=93
python -m pytest -q tests/test_r2_conformance_oracle.py
python -m pytest -q tests/test_check_ledger.py tests/test_check_work_order_disposition.py tests/test_check_pkl.py tests/test_check_work_order_scope.py
```

Exact hygiene test paths may be corrected from repo discovery; every deviation and
all decisive output must be recorded in the report.

## Acceptance criteria

- [ ] Sections A-J match the charter's Part A report shape and every material claim traces to pasted command output.
- [ ] Status labels are limited to VERIFIED, UNVERIFIED, BLOCKED, and NEEDS-INPUT.
- [ ] The conformance oracle is implementation-independent and passes its own invariant-frame and boundary-of-trust review.
- [ ] Both attempts receive mirror-image analysis; neither implementation is treated as the specification.
- [ ] Namespace, work-state, documentation, architecture, and lineage collisions are exhaustively mapped.
- [ ] The consolidation program is ordered, gated, reversible, and marks every human-gated surface STOP-FOR-HUMAN.
- [ ] Scope is limited to allowed paths; no shared comparison branch or PR is mutated.
- [ ] Fable DONE block includes fresh evidence.
- [ ] PKL update is either completed after ratified implementation or explicitly recorded as not required for Part A.
- [ ] Part A artifacts are committed and the session stops pending recorded human ratification; Part B is not begun.

## Model-tier rationale

Strong reasoning is required because this investigation compares two large,
independent safety-surface implementations, derives a neutral behavioral oracle,
adjudicates formal and performance obligations, and prepares human-gated decisions.

## Notes

[FABLE • FULL • verification: DIRECT • task: R2 consolidation Part A]

```yaml
fable_gate:
  goal: "Produce the independent Codex Part A decision package and conformance oracle."
  assumptions:
    - "The user's 2026-07-16 instruction to execute PARTAKICKOFF.md authorizes Part A only."
    - "The accepted ADR, invariant corpus, and treadmill charter are the behavioral oracle; neither implementation is."
    - "Distinct Codex artifact paths preserve the kickoff's investigator-independence requirement."
  approach: "Freeze and inventory refs; derive and cross-run the oracle; characterize, benchmark, and adversarially cross-verify both attempts; synthesize Sections A-I with direct evidence in Section J."
  out_of_scope:
    - "Part B implementation before recorded human ratification"
    - "Mutating any shared comparison branch, pull request, live-mode setting, or broker surface"
    - "Reading another investigator's report, PR comments about their findings, or investigator commits"
  done_when:
    - "The Part A report and oracle are committed on the consolidation branch"
    - "Section I decisions are surfaced to the human"
    - "Execution stops before Part B"
  blast_radius: "Part A writes only its work-order, report, and tests; future Part B would touch human-gated order-intent and event-truth surfaces and remains blocked."
```

The human activated Part A by directing Codex on 2026-07-16 to execute the attached
`PARTAKICKOFF.md`; this is not ratification of Section I and does not activate Part B.

Identifier inventory before drafting found WO-0001..WO-0036 and WO-0100..WO-0105
claimed across refs; WO-0106 was the next unused work-order id. No REV id is claimed
for this investigator report; it uses the consolidation artifact path named above.

## Completion disposition

Complete this section only after Part B closure or an explicit campaign disposition.

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
- [ ] DELETED
- [ ] SUPERSEDED
- [ ] ABANDONED

## Distillation checklist

- [ ] Durable product facts captured in PKL or not needed.
- [ ] Architecture decisions captured in ADR or not needed.
- [ ] Failure lessons captured in drift/error log or not needed.
- [ ] Compact work result created if future retrieval value exists.
- [ ] Ledger updated.
- [ ] Raw work order marked for archive or deletion.

## Deletion decision

Deletion reason: Retain while the two-part consolidation campaign and its human
ratification gate remain active.
