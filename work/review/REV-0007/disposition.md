---
type: Review Disposition
rev_id: REV-0007
campaign_id: CAMPAIGN-0001
verdict_received: BLOCK
disposition_status: VERIFIED
remediation_status: DEFERRED-GATED (defense-in-depth) + doc-fix
verified_env: python 3.12.3 (venv), frozen base b600101 == HEAD app/ (byte-identical)
date: 2026-07-10
---

# Disposition — REV-0007 (EVENTS, event sourcing)

Reviewer: GPT-5 Codex, verdict **BLOCK** (two P1s). Author-side verification reproduced both in 3.12
and finds the **code facts CONFIRMED but the severities overstated**: both downgrade **P1 → P2**, and
F002's core reachability claim is **REFUTED for every production flow**.

## Per-finding verdicts

### REV-0007-F001 — dual-store parity omits order-status (reviewer P1) → **PARTIAL**, **P2**
Confirmed + reproduced: `verify_dual_store_parity` / `verify_dual_store_readmodel_parity`
(`app/events/replay.py`) have **no order-status field**, so asymmetric per-store appends fold to
`CANCELED` vs `SUBMITTED` while both verifiers still return `ok=True`.
- **Why P2:** this is the **disclosed scope-note deferral** the packet itself pointed at
  (`replay.py:121-141`, "NOT covered here: … order-status/spawn projection … a deliberate, documented
  deferral"); **ADR-004's required tests do not mandate order-status parity**; and order-status
  cross-store parity **is** covered by a runnable mechanism —
  `tests/test_wo0007a_stage4_dual_store_parity.py` drives production scripts into both stores and
  asserts identical event streams. The exhibited divergence is **single-writer-unreachable** (it
  requires asymmetric appends the single writer never produces).
- **Legit follow-up:** post-WO-0007b read-flip, `project_order_status` is now the *authoritative*
  read, so the scope note's "co-written read-model" justification is slightly stale. Adding an
  order-status projection to the runtime read-model verifier is a real hardening item (P2).

### REV-0007-F002 — append boundary not semantically closed (reviewer P1) → **PARTIAL (reachability REFUTED)**, **P2**
Confirmed code facts: `project_order_status` folds pure latest-lifecycle-event-wins with **no
`ORDER_TRANSITIONS` / terminality guard**; reproduced a malformed FILL (`quantity=None`) persisting +
folding to `filled_quantity=0` (yet fatal to the position fold — an internal inconsistency), and a
`[CANCELED, SUBMITTED]` sequence resurrecting a terminal order.
- **Decisive refutation:** the public `append_execution_event` has **zero production callers**
  (`grep -rn "\.append_execution_event(" app/` → none; only 4 test files). Every production write goes
  through internal helpers fed by **validated, transition-guarded planners** — `plan_append_fill`
  rejects a bad-value FILL via `fill_value_reason` *before* building the event; `plan_transition_order`
  rejects any edge not in `ORDER_TRANSITIONS` (terminal states have empty transition sets; repro
  confirms `CANCELED→SUBMITTED` → reject). So a malformed FILL / illegal transition **cannot enter the
  log in production**. This is precisely the deferral **INV-075** (registered when we accepted ADR-008)
  consciously guards.
- **Genuine doc-accuracy nit (worth fixing):** ADR-008 "Truth model" / INV-075 wording ("folds by
  `sequence` + the `ORDER_TRANSITIONS` graph", "bounded by the legal-transition graph") reads as if
  `project_order_status` itself consults the graph — it does **not**; the bound is enforced at the
  **write path** (`plan_transition_order`). Fix the wording to name the write path as the guard.

## Disposition
- **F001:** PARTIAL P2 → **gated** hardening WO (event-log-truth surface): add an order-status
  projection to the runtime dual-store read-model verifier + refresh the stale scope-note
  justification. Test-first, Codex re-review.
- **F002:** PARTIAL P2 → **doc fix** (correct ADR-008 / INV-075 wording to attribute the transition
  bound to the write path — an ADR amendment, human-gated) + **optional** defense-in-depth: validate
  event-type-required fields + lifecycle legality at the append boundary (and reconcile the malformed-
  FILL asymmetry between the status fold and position fold). No live-bug remediation required.

## Gate
G-D's BLOCK is **downgraded**: no production-reachable data-integrity defect — the write-path guards
+ INV-075 tripwire hold. Remaining items are hardening + doc-accuracy. Evidence:
`scratchpad/repro_f001.py`, `repro_f002.py` (3.12).
