---
type: Work Order
title: "P1-3 closure: re-measure R2 scaling on current master; bound stress-scale startup; set beta-scale budget"
status: DRAFT
work_order_id: WO-0118
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
owner: Ameen (batched at REV-0029 disposition) / implementer: Codex session 2
created: 2026-07-20
gated_surface: none expected; any new index/DDL or gate-limit change requires explicit operator approval (D9 precedent)
---

# Work Order: performance follow-up — measure first, optimize only if the data says so

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

- [ ] **Phase 1 — measure (always runs):** on current master, fresh venv, record with pasted
      output: (a) `python -m tests.performance.r2_scaling_gate` (target scale, 3 runs — report
      spread, not one lucky run); (b) the same with `R2_STRESS=1` (the 1,000-symbol corpus);
      (c) the Claude-ported gate; (d) SELECT counts + `EXPLAIN QUERY PLAN` confirming no
      unrelated full scans. The REV-0029 stress numbers predate Cluster E — this phase
      establishes whether the convexity still exists at all.
- [ ] **Phase 2 — optimize (ONLY if Phase 1 shows material stress convexity, e.g. startup
      scaling far superlinear in corpus size):** behavior-preserving changes per the Cluster E
      contract — no retention predicate, action authority, scaling threshold, or human-gated
      transition may change; dual-store parity maintained; every change mutation-pinned or
      covered by the existing parity/oracle corpus. Any NEW index or DDL requires an explicit
      recorded operator approval line before it lands (D9 precedent).
- [ ] **Phase 3 — budget (always runs):** record the beta-scale performance budget: expected
      real-data cardinality (cross-reference WO-0115's inventory if available), the measured
      headroom against it, and a stress budget in the gate (as a NEW `R2_STRESS` assertion or
      documented threshold). **Raising or loosening ANY existing limit is operator-gated and
      requires independent review — "no re-budget, no silent green" (REV-0029 disposition).**
- [ ] Full native gate green: `ruff` + `mypy app/` + `lint-imports` + `pytest -q` + both
      oracles + hardening gates + the scaling gate itself.
- [ ] Close-out ships with the work; REV-0029 P1-3 line updated from "→ perf WO (batched)" to
      closed-with-evidence in the disposition's successor record (a dated note in this WO's
      close-out + ledger row; do not rewrite the historical disposition file).

## Acceptance criteria

- [ ] Phase 1 evidence pasted for all three gates + plans; a clear statement of whether the
      stress convexity survived Cluster E.
- [ ] If Phase 2 ran: red-first/mutation evidence that semantics are unchanged (parity suite,
      oracles, hostile corpus all green; no gate limit touched).
- [ ] Beta-scale budget recorded in `pkl/architecture/testing-model.md` + the gate.
- [ ] Independent review queued if ANY `app/store/*` line changed (Cluster E precedent:
      store-surface perf work rides the review gate before beta reliance). Measurement-only
      outcome (no code change) needs no REV packet — the evidence table is the deliverable.
- [ ] Fable DONE block: `VERIFIED` with pasted evidence, or `BLOCKED` naming the wall.

## Stop conditions

Stop and report (no fix) if: any optimization would require touching a retention predicate,
authority rule, or event-log semantics; measured behavior differs between stores; a limit
looks wrong and re-budgeting tempts — that is an operator decision, never an edit. Rollback:
revert the WO's commits; no data or schema to unwind unless a D9-approved index landed (drop
is the documented rollback for an additive index).

## Model-tier rationale

`mid` — measurement discipline plus bounded, precedent-guided optimization; the hard semantic
rails are already pinned by the existing parity/oracle corpus.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.
