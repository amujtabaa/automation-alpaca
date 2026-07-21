---
type: Work Order
title: "P1-3 closure: re-measure R2 scaling on current master; bound stress-scale startup; set beta-scale budget"
status: CLOSED
work_order_id: WO-0118
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen (batched at REV-0029 disposition) / implementer: Codex session 2
created: 2026-07-20
gated_surface: none expected; any new index/DDL or gate-limit change requires explicit operator approval (D9 precedent)
---

# Work Order: performance follow-up — measure first, optimize only if the data says so

[FABLE • FULL • verification: DIRECT • task: WO-0118 performance stress-scale closure]

```yaml
fable_gate:
  goal: "Re-measure current scaling at target and stress size, optimize only on repeatable material convexity, and freeze an explicit beta-scale budget without loosening any limit."
  assumptions:
    - "WO-0114 is integrated at this branch base through its REVIEW-stage commits, so the shared app/store sequencing gate is clear."
    - "WO-0115 has no ratified source database path; REALISTIC is the declared beta design target, not an observed-paper inventory, and STRESS supplies measured 10x cardinality headroom."
    - "Wall-clock evidence is interpreted across three fresh runs; one noisy result cannot trigger Phase 2 or a budget change."
  approach: "Activate first; measure all target/stress gates in a fresh OS-temp Python 3.12 environment; add a red-first executable budget contract; skip store optimization unless repeated evidence proves material convexity; then run the full native and AI-OS gates before atomic close-out."
  out_of_scope:
    - "Any new index, DDL/schema change, or migration without a new explicit D9 approval line."
    - "Any relaxation of the 3x runtime, 12x startup, or 2 MiB projection limits."
    - "Any retention predicate, action authority, event-log truth, human-gated transition, or execution behavior change."
    - "Any live trading, Alpaca credential use, or real-paper database access."
  done_when:
    - "Three-run target and stress evidence plus Claude-ported gate evidence records spreads, SELECT counts, query plans, and the post-Cluster-E convexity verdict."
    - "The gate and testing-model PKL name the beta target, 10x stress cardinality, headroom, and unchanged thresholds, with a failure-capable budget pin."
    - "Full native, oracle, hardening, scaling, scope, disposition, ledger, PKL, and hygiene gates have fresh evidence."
    - "Status, disposition, ledger, batch scoreboard, and file move close atomically."
  blast_radius: "tests/performance/**, pkl/architecture/testing-model.md, and work/**; app/store/** only if Phase 1 independently triggers Phase 2"
```

> **Sequencing gate:** do NOT execute while a live WO-0114 (Lane P) branch is unmerged — both
> touch `app/store/*`. If the operator's launch message says Lane P is pending/unratified,
> this WO is collision-free and may run now. Findings-only interaction with the running
> audit session (no shared files).

## Goal

Convert REV-0029 P1-3 from an open finding to a closed, evidence-backed verdict: current
master's scaling behavior re-measured at target AND stress scale, any remaining material
convexity bounded by behavior-preserving optimization, and an explicit beta-scale budget
recorded — with zero silent re-budgeting.

## Context packet

Read only these first:

- `CLAUDE.md` + `work/review/REV-0029/result.md` §P1-3 (the original finding: structural green,
  round-1 wall-clock red, stress startup ~72-76x at the 1,000-symbol/100,002-event corpus)
- `work/review/REV-0029/disposition.md` (P1-3 "ACCEPT-WITH-CHANGES-shaped: dedicated perf WO,
  no re-budget, no silent green") + `work/review/REV-0033/disposition.md` (current state:
  default gate `passed: true`, runtime 1.0604 ≤ 3.0, startup 8.1241 ≤ 12.0, selects 9.1022 ≤ 12.0)
- `docs/adr/ADR-010-execution-envelope.md` §3 Cluster E (the behavior-preserving optimization
  precedent: indexed identity arms, dedupe-by-event-id, exclusion-after-composition,
  event-sequence order — none of the retention semantics changed)
- `tests/performance/r2_scaling_gate.py` (+ `r2_scaling_gate_claude_ported.py`): limits
  RUNTIME 3.0 / STARTUP 12.0 / 2MiB projection peak; `R2_STRESS=1` corpus; SELECT tracing +
  `EXPLAIN QUERY PLAN` unrelated-full-scan detection
- `app/store/sqlite.py` (projection loader + `initialize()` startup path), `app/store/core.py`
  (`project_envelope_obligation`), `pkl/architecture/testing-model.md`

## Allowed paths

```yaml
allowed_paths:
  - tests/performance/**       # gate extensions, stress budgets, measurement harness
  - app/store/sqlite.py        # ONLY if Phase 2 triggers; behavior-preserving per Cluster E rules
  - app/store/memory.py        # parity twin of any sqlite change
  - app/store/core.py          # read-mostly; changes need the same Cluster E constraints
  - pkl/architecture/testing-model.md
  - work/**                    # close-out, evidence, review packet
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/models.py              # no vocabulary/semantic surface in a perf WO
  - app/facade/**
  - app/api/**
  - app/monitoring.py
  - app/reconciliation.py
  - docs/adr/**                # a needed amendment is a proposal for the operator, not an edit
```

## Required behavior

- [x] **Phase 1 — measure (always runs):** on current master, fresh venv, record with pasted
      output: (a) `python -m tests.performance.r2_scaling_gate` (target scale, 3 runs — report
      spread, not one lucky run); (b) the same with `R2_STRESS=1` (the 1,000-symbol corpus);
      (c) the Claude-ported gate; (d) SELECT counts + `EXPLAIN QUERY PLAN` confirming no
      unrelated full scans. The REV-0029 stress numbers predate Cluster E — this phase
      establishes whether the convexity still exists at all.
- [x] **Phase 2 — optimize (ONLY if Phase 1 shows material stress convexity, e.g. startup
      scaling far superlinear in corpus size):** behavior-preserving changes per the Cluster E
      contract — no retention predicate, action authority, scaling threshold, or human-gated
      transition may change; dual-store parity maintained; every change mutation-pinned or
      covered by the existing parity/oracle corpus. Any NEW index or DDL requires an explicit
      recorded operator approval line before it lands (D9 precedent).
      **Outcome: condition not triggered; Phase 2 was intentionally skipped.**
- [x] **Phase 3 — budget (always runs):** record the beta-scale performance budget: expected
      real-data cardinality (cross-reference WO-0115's inventory if available), the measured
      headroom against it, and a stress budget in the gate (as a NEW `R2_STRESS` assertion or
      documented threshold). **Raising or loosening ANY existing limit is operator-gated and
      requires independent review — "no re-budget, no silent green" (REV-0029 disposition).**
- [x] Full native gate green: `ruff` + `mypy app/` + `lint-imports` + `pytest -q` + both
      oracles + hardening gates + the scaling gate itself.
- [x] Close-out ships with the work; REV-0029 P1-3 line updated from "→ perf WO (batched)" to
      closed-with-evidence in the disposition's successor record (a dated note in this WO's
      close-out + ledger row; do not rewrite the historical disposition file).

## Acceptance criteria

- [x] Phase 1 evidence pasted for all three gates + plans; a clear statement of whether the
      stress convexity survived Cluster E.
- [x] If Phase 2 ran: red-first/mutation evidence that semantics are unchanged (parity suite,
      oracles, hostile corpus all green; no gate limit touched).
- [x] Beta-scale budget recorded in `pkl/architecture/testing-model.md` + the gate.
- [x] Independent review queued if ANY `app/store/*` line changed (Cluster E precedent:
      store-surface perf work rides the review gate before beta reliance). Measurement-only
      outcome (no code change) needs no REV packet — the evidence table is the deliverable.
      **Outcome: not applicable; no `app/store/*` line changed.**
- [x] Fable DONE block: `VERIFIED` with pasted evidence, or `BLOCKED` naming the wall.

## Stop conditions

Stop and report (no fix) if: any optimization would require touching a retention predicate,
authority rule, or event-log semantics; measured behavior differs between stores; a limit
looks wrong and re-budgeting tempts — that is an operator decision, never an edit. Rollback:
revert the WO's commits; no data or schema to unwind unless a D9-approved index landed (drop
is the documented rollback for an additive index).

## Model-tier rationale

`mid` — measurement discipline plus bounded, precedent-guided optimization; the hard semantic
rails are already pinned by the existing parity/oracle corpus.

## Execution evidence — 2026-07-21

### Environment

Fresh OS-temp environment: `C:\Users\amujt\AppData\Local\Temp\codex-wo0118-py312`.

```text
CPython 3.12.13 (MSC v.1944 64 bit, AMD64)
Windows-11-10.0.26200-SP0
SQLite 3.50.4
pip 25.0.1
fastapi=0.139.0 pydantic=2.13.4 pytest=9.1.1
ruff=0.15.20 mypy=2.2.0 import-linter=2.13
pip check: No broken requirements found.
```

The constrained install used `requirements.txt` with `constraints.txt`. No Alpaca credentials,
paper database, network broker call, or live/shadow trading mode was used.

### Phase 1 — fresh target/stress measurement

Canonical target runs (`R2_STRESS` absent), each exit 0:

| Run | Runtime p95 ratio | Startup elapsed ratio | Startup SELECT ratio | Runtime SELECTs | Projection peak |
|---|---:|---:|---:|---:|---:|
| 1 | 0.758941x | 8.984696x | 9.102190x | 18 → 18 | 310,040 B |
| 2 | 1.022693x | 9.169887x | 9.102190x | 18 → 18 | 310,256 B |
| 3 | 0.667735x | 9.417490x | 9.102190x | 18 → 18 | 310,256 B |

Spread: runtime `0.667735–1.022693x` (median `0.758941x`); startup elapsed
`8.984696–9.417490x` (median `9.169887x`); SELECT ratio exactly `9.102190x`.

Canonical stress runs (`R2_STRESS=1`), each exit 0. The comparison is the 100-symbol /
1,001-Envelope / 10,002-event / 1,000-recovery design target versus the 1,000-symbol /
10,001-Envelope / 100,002-event / 10,000-recovery stress corpus.

| Run | Runtime p95 ratio | Startup elapsed ratio | Startup SELECT ratio | Runtime SELECTs | Stress startup |
|---|---:|---:|---:|---:|---:|
| 1 | 1.142179x | 11.480315x | 9.901363x | 18 → 18 | 7,085.388 ms |
| 2 | 0.977006x | 11.063887x | 9.901363x | 18 → 18 | 7,018.490 ms |
| 3 | 1.026324x | 10.807658x | 9.901363x | 18 → 18 | 6,749.839 ms |

Spread: runtime `0.977006–1.142179x` (median `1.026324x`); startup elapsed
`10.807658–11.480315x` (median `11.063887x`); SELECT ratio exactly `9.901363x`.

The Claude-ported gate also exited 0 at target (runtime `0.801569x`, startup `8.818945x`,
SELECT `9.102190x`) and stress (runtime `1.008816x`, startup `10.701036x`, SELECT
`9.901363x`). All canonical and ported reports had `unrelated_full_scans: []`. EXPLAIN used
bounded seeks through `idx_envelopes_symbol`, `idx_exec_events_envelope`,
`idx_exec_events_symbol_type`, `idx_orders_symbol`, `idx_exec_events_order`,
`idx_recoveries_local_order`, and primary-key indexes; scoped order-by operations alone used a
temporary B-tree.

**VERIFIED Phase-1 verdict:** the pre-Cluster-E `72–76x` stress startup convexity did not
survive. Current startup work is approximately linear for approximately 10x facts and remains
inside the unchanged 12x ceiling. Phase 2 did not trigger: zero `app/store/**` changes, zero D9
index/DDL request, and no independent store-surface review packet.

### Phase 3 — red/green and mutation proof

```yaml
fable_fix:
  symptom: "The scaling scripts enforced ratios but did not expose one shared, executable beta target/stress cardinality and threshold contract."
  root_cause: "Cardinality and limits lived as duplicated script-local facts, so drift or removal of one stress assertion was not independently pinned."
  evidence: "Initial targeted pytest failed during collection because tests.performance.r2_scaling_budget did not exist."
  fix: "Add one shared budget applicator used exactly once by both gates; make cardinality and stress-contract checks part of passed; emit limits and measured ratio margin; record the contract in testing-model PKL."
  regression_test: "tests/performance/test_r2_scaling_budget.py"
  red_green_verified: true
  attempt: 1
```

```text
RED: ImportError: cannot import name 'r2_scaling_budget' from 'tests.performance'
GREEN: 6 passed
MUTANT: disable the ported gate's apply_beta_scale_budget call → 1 failed, 1 passed
RESTORED: 6 passed
POST-CHANGE GATES: canonical target/stress and ported target/stress all exit 0;
  cardinality gates=true, stress contract complete=true, limits_changed=false.
```

### Full validation and close-out gates

All Python validation used the fresh OS-temp CPython 3.12 environment and OS-temp pytest
scratch; the repository root received no pytest cache or basetemp directory.

```text
ruff check .
  All checks passed.

ruff format --check tests/performance/r2_scaling_budget.py
  tests/performance/r2_scaling_gate.py
  tests/performance/r2_scaling_gate_claude_ported.py
  tests/performance/test_r2_scaling_budget.py
  4 files already formatted.

mypy app/
  Success: no issues found in 70 source files.

lint-imports
  Contracts: 6 kept, 0 broken; analyzed 99 files and 484 dependencies.

pytest -q tests/r2_conformance_oracle.py
  61 passed.

pytest -q tests/test_r2_conformance_oracle_claude.py
  22 passed, 6 skipped.

pytest -q tests/test_review_hardening_gates.py
  14 passed.

pytest -q tests/performance/test_r2_scaling_budget.py
  6 passed.

full pytest, cache disabled, OS-temp basetemp
  3980 collected; 3968 passed, 11 skipped, 1 xfailed in 309.3s.

AI-OS close-out tree
  INSTALL CHECK PASSED
  VERSION CHECK PASSED: v0.9.1
  LEDGER CHECK PASSED
  PKL CHECK PASSED
  DISPOSITION CHECK PASSED
  SCOPE CHECK PASSED
  HYGIENE REPORT: 0 violations, 3 pre-existing active-WO size advisories
  git diff --check: clean
```

Repository-wide `ruff format --check .` remained non-green at six files already present at
the `f4104fe` branch base: `app/recorder/__init__.py`, `app/recorder/models.py`,
`app/recorder/store.py`, `harness/bootstrap.py`, `tests/test_tape_recorder.py`, and
`work/review/AUDIT-0002-priorwork/probe_review_integrity.py`. They are outside WO-0118's
edits; none was reformatted. The four changed Python files passed the scoped format check.
The hygiene advisories name review-gated WO-0114, WO-0121, and WO-0127; no hygiene violation
was introduced.

## Fable done

```yaml
fable_done:
  task: "WO-0118 performance stress-scale closure and beta budget"
  done_when_results:
    - item: "Three-run target and stress evidence plus both gate implementations establish current scaling behavior."
      status: MET
    - item: "The post-Cluster-E convexity decision follows repeated evidence without an unapproved store, schema, DDL, or index change."
      status: MET
    - item: "One failure-capable shared contract freezes target/stress cardinality and unchanged 3x, 12x, and 2 MiB limits in code and PKL."
      status: MET
    - item: "Native, oracle, hardening, full-suite, AI-OS, scope, disposition, ledger, PKL, and hygiene gates have fresh evidence."
      status: MET
    - item: "Status, disposition, ledger, batch scoreboard, and file move close atomically."
      status: MET
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    app_store_changes: false
    schema_or_index_changes: false
  evidence:
    - "Canonical target and stress measurements passed 3 of 3 runs each; both Claude-ported runs passed."
    - "Stress startup spread 10.807658-11.480315x; SELECT growth 9.901363x; unrelated scans empty."
    - "Budget pin was red first, green at 6 passed, mutation-red at 1 failed and 1 passed, and restored green."
    - "Full OS-temp suite: 3980 collected; 3968 passed, 11 skipped, 1 expected xfail."
    - "AI-OS install, version, ledger, PKL, disposition, scope, and hygiene checks passed with zero violations."
  status: VERIFIED
```

## Completion disposition

Applied: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.
