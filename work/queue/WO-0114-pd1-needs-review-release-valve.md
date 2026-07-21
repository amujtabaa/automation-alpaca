---
type: Work Order
title: "PD-1: needs_review reconciliation release valve (human-gated, event-truth)"
status: DRAFT
work_order_id: WO-0114
wave: post-R2 beta-prep
model_tier: strong
risk: high
disposition: []
owner: Ameen (ratifies) / planning seat drafted 2026-07-20 / implementer TBD
created: 2026-07-20
gated_surface: event-log truth, recovery FSM vocabulary, operator control API
---

# Work Order: PD-1 — the needs_review reconciliation release valve

> **RATIFIED 2026-07-20 (Ameen, structured decision prompt; recorded in
> `PD1-R2-PLANNING-PACKAGE.md` §2):** D-PD1-1 = hybrid-honest; D-PD1-2 = `operator_reconciled`;
> D-PD1-3 = **API + cockpit control** (the cockpit button invokes ONLY the typed FastAPI
> command); D-PD1-4 = separate ingestion + valve commands, both in this WO. Implementation may
> activate per normal WO flow. Still required before any beta reliance: its own independent
> cross-model review packet (`REV-00xx`, next free id) with `ACCEPT`/`ACCEPT-WITH-CHANGES`.
> Independent of WO-0115 (backfill verification); neither expands the other.

## Goal

Give the recovery FSM an honest, human-gated exit from `needs_review` — an operator
attestation command that releases ONE `SubmitRecoveryRecord`'s quarantine contribution after
venue truth is reconciled, without ever manufacturing economic truth.

## Context packet

Read only these first:

- `CLAUDE.md` (safety core; human-gated surfaces)
- `work/review/REV-0029/result.md` — "PD-1 assessment" (binding constraints)
- `work/review/CAMPAIGN-0002-claude/BLOCKED-DECISIONS.md` — PD-1 memo + 2026-07-18 correction
- `docs/adr/ADR-008-order-status-event-provenance.md` + `docs/adr/ADR-010-execution-envelope.md` §3/§6
- `docs/INVARIANTS.md` INV-090/INV-091 (+ ADR-001 permanent-latch contract, `pkl/safety/invariants-rationale.md`)
- `app/models.py:885-950` (recovery vocabulary/record), `app/models.py:488-513` (EventSource/EventAuthority)
- `app/store/core.py` (`recovery_status_event:2546`, `project_envelope_obligation:1401`)
- `app/store/memory.py` + `app/store/sqlite.py` (recovery persistence; `needs_review` consumers)
- `tests/test_wo0036_r2_close_and_recovery_ownership.py` + `tests/test_wo0108_rev0029_remediation.py` (current pins)

## Allowed paths

```yaml
allowed_paths:
  - app/models.py            # status vocabulary + (per D-PD1-1) provenance enums
  - app/store/core.py        # FSM legality, projection contribution removal, shared planner
  - app/store/base.py        # command contract
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/**            # typed command + DTO + error mapping
  - app/api/routes_trading.py
  - cockpit/**               # D-PD1-3: release control; typed API client ONLY — no store/broker/alpaca imports
  - app/monitoring.py        # operator visibility only (no recovery-loop behavior change)
  - tests/**                 # new test module + updated pins ONLY where behavior legitimately changed
  - docs/adr/ADR-012-*.md    # new ADR (ADR-011 is reserved for the W4 entry-envelope seed)
  - docs/adr/ADR-008-order-status-event-provenance.md   # amendment iff D-PD1-1 adds vocabulary
  - docs/INVARIANTS.md       # new INV-096 + INV-090 cross-reference
  - pkl/safety/invariants-rationale.md
  - work/**                  # close-out, review packet, ledger
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/adapters/**          # ZERO broker calls: the valve never submits/cancels/replaces at the venue
  - app/reconciliation.py    # the reconciler must keep refusing to auto-resolve (reconciliation.py:19-32)
  - .github/workflows/**
```

## Required behavior

- [ ] **Vocabulary (per D-PD1-2):** one NEW terminal cleanup status (candidate names in the
      decision register; never reopen to `unresolved`), added to `RECOVERY_STATUSES` /
      `RECOVERY_TRANSITIONS` (`needs_review → <new>` is the only new edge) and
      `recovery_status_event`; a distinct audit `EventType` (e.g. `submit_recovery_reconciled`).
      The recovery loop still selects only `{RECOVERY_UNRESOLVED}` (monitoring.py:2869) and can
      never touch the record again. No SQLite DDL is required (`cleanup_status` is unconstrained
      TEXT, sqlite.py:353-369) — state so in the ADR, don't invent a migration.
- [ ] **Attestation contract:** the command carries actor, non-empty reason, evidence reference,
      and a full identity echo — `recovery_id`, `local_order_id`, `broker_order_id`
      (`client_order_id` when the row has one), `symbol`, `side` — plus the attested facts:
      broker-terminal state and cumulative venue filled quantity for that exact broker order.
      Any mismatch with the durable row fails closed with zero writes.
- [ ] **Fail-closed contradictions:** non-terminal attested broker state; malformed/incomplete
      evidence; identity mismatch (wrong recovery/order/broker-id/symbol/side, or
      envelope/owner lineage that no longer matches the projection); cumulative-fill parity
      failure — attested cumulative quantity ≠ the sum of canonical FILL events for that
      `(local_order_id, broker_order_id)` in event truth (zero-fill terminal evidence must match
      zero canonical fills); record not in `needs_review` (see idempotency below).
- [ ] **Truth rule:** the transition writes NO fill and moves NO position. Discovered fills enter
      truth only as canonical deduplicated FILL events (`plan_append_fill`, dedupe
      `fill:{order_id}:{source_fill_id}`) with honest provenance per D-PD1-1/D-PD1-4 — via a
      SEPARATE ingestion command if D-PD1-4 ratifies the recommended split. Parity is checked
      against event truth at valve time, so ingestion (which legitimately moves position) always
      precedes release, and the un-released interval stays quarantined (safe).
- [ ] **Atomic revalidation:** all checks + status write + audit `Event` (payload
      `{actor, reason, evidence_ref, attested facts}`) + `ExecutionEvent` (provenance per
      D-PD1-1) happen in ONE store-lock/transaction hold, following the
      `_write_emergency_reduce_override_locked` template (sqlite.py:7253-7285). There is no CAS
      token on recovery rows (base.py:936-943) — the lock-serialized read-validate-write IS the
      concurrency mechanism; a concurrent transition loses cleanly (`RecoveryTransitionError`
      surfaces, zero partial writes).
- [ ] **Idempotency:** an exact repeat of an already-applied attestation returns success with no
      new writes; a DIFFERENT attestation against an already-released record is a 409-class
      refusal. Replay/restart never double-applies (SQLite reopen parity).
- [ ] **Projection contribution removal:** the released record leaves
      `needs_review_child_order_ids` (core.py:1780-1800), `_order_needs_review_*`
      (memory.py:948 / sqlite.py:1829), and every `RECOVERY_OPEN_STATUSES` scan. Release lifts
      the symbol's sell side ONLY if no other predicate holds — another open recovery, strict
      retention, malformed-ambiguity, venue obligation, TIMEOUT_QUARANTINE, or the ADR-001
      overfill latch (which is permanent and is NOT touched by this WO) each independently keep
      the quarantine.
- [ ] **Boundary:** operators and the cockpit reach this only through the typed facade
      command + `POST` route (`Depends(get_command_facade)`, `X-Actor`, `FacadeError` → 404/409/422
      mapping). The D-PD1-3 cockpit control calls the typed API client only — no route→store,
      no route→broker, no UI-owned state; an AppTest pin proves the button renders
      server-classified outcomes and imports no store/broker module.
- [ ] **Docs ship with the change:** new ADR-012 (valve semantics + decisions as ratified),
      ADR-008 amendment iff vocabulary added, INV-096, `pkl/safety/invariants-rationale.md`,
      and the hardening gates (`tests/test_review_hardening_gates.py` enum-total/producer-consumer)
      extended to the new status + consumers.

## Required tests

All red-first, BOTH stores, SQLite reopen/restart parity where marked (R):

- [ ] Denial without evidence/actor/reason; malformed evidence; non-terminal broker state.
- [ ] Wrong identity: recovery id, local order, broker id, symbol, side, envelope/owner lineage.
- [ ] Cumulative parity: zero-fill terminal, partial fills, fully accounted fills, contradiction
      (attested ≠ event truth) — each refused/accepted correctly. (R)
- [ ] Discovered-fill path (per D-PD1-4): canonical dedupe under retry AND replay — one FILL,
      one position movement, never two. (R)
- [ ] Valve never moves position: position projection byte-identical before/after a successful
      release with fully-accounted fills. (R)
- [ ] Concurrency: valve vs concurrent monitoring/recovery tick; interleaved double-submit —
      exactly one applies, loser fails closed with zero partial writes.
- [ ] Idempotent repeat (same attestation) and 409 on conflicting re-attestation. (R)
- [ ] Contribution-only release: second open recovery (or malformed obligation) on the same
      symbol keeps stage/claim/direct-SELL/flatten quarantine; release of the LAST predicate
      lifts them (assert via the existing WO-0108/0109 rails, not new path-local checks). (R)
- [ ] ADR-001 latch survives a release (permanent-latch contract intact).
- [ ] Zero venue calls: adapter spy proves no submit/cancel/replace from the valve path.
- [ ] Audit/provenance: actor/reason/evidence durably visible; open-recoveries operator view
      drops the record; full record remains queryable. (R)
- [ ] Existing pins updated ONLY where the old "terminal forever" claim legitimately changed
      (e.g. `test_needs_review_stays_in_the_open_operator_view`) — never weakened.

## Required commands

```bash
ruff check . && ruff format --check .
mypy app/
lint-imports
pytest -q                                   # full suite
pytest -q tests/r2_conformance_oracle.py tests/test_r2_conformance_oracle_claude.py
pytest -q tests/test_review_hardening_gates.py
```

## Acceptance criteria

- [ ] All required behavior implemented per the RATIFIED D-PD1-1..4 (no improvised semantics).
- [ ] Tests above green both stores + restart; mutation checks on the parity and identity rails.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable FULL gate + DONE block with fresh pasted evidence.
- [ ] Independent cross-model review packet dispositioned ACCEPT/ACCEPT-WITH-CHANGES
      **before** any beta-relevant reliance; ADR-012 accepted by Ameen.
- [ ] Close-out ships with the work: status flip, disposition, ledger, PKL/ADR/INV refresh.

## Stop conditions

Stop and record a decision gap (no code) if: any check requires weakening an existing pin;
the design would need the valve to write position or synthesize a fill; provenance cannot be
recorded honestly under the ratified D-PD1-1; a second semantic gap surfaces (e.g. an ADR-001
release valve, a `resolved_canceled` reopen path) — that is a NEW work order, never scope creep
here. Rollback: revert the WO's commits; no data migration exists to unwind.

## Model-tier rationale

`strong` — event-truth vocabulary, dual-store atomic command, adversarial concurrency/replay
surface; same class as WO-0108/0113.

## Notes

- Blocking inputs: D-PD1-1 (provenance), D-PD1-2 (status name), D-PD1-3 (API-only vs cockpit),
  D-PD1-4 (fill ingestion split) — see `work/queue/PD1-R2-PLANNING-PACKAGE.md`.
- The valve releases ONE record's contribution. It is explicitly NOT: an ADR-001 overfill-latch
  release, a TIMEOUT_QUARANTINE resolver, a venue command, or a backfill/repair tool.
- `SubmitRecoveryRecord` has no actor/resolution columns (models.py:931-950); the audit-event
  path avoids any table migration. If Ameen instead wants resolution columns on the row, that
  is a schema change requiring its own explicit approval line before implementation.

## Completion disposition

Complete after merge/closure per template; expected: `[ADR_CREATED, PKL_UPDATED,
RESULT_SUMMARY_KEPT]`.
