---
type: Work Order
title: "Durable deduped needs-review record for persistently malformed cancel lineages (REV-0037 P2-1)"
status: QUEUED
work_order_id: WO-0135
wave: post-ULTRA advisory follow-up (REV-0037 P2-1)
model_tier: strong (LOCAL Codex — event-log-truth surface)
risk: medium
owner: Ameen / implementer: Codex local session
created: 2026-07-22
gated_surface: event-log truth (a NEW condition appends to the append-only log) — human-gated; ends at status REVIEW with REV-0040 staged for the Claude seat. NO schema migration and NO new event vocabulary (reuse path) → no mid-session DDL/vocabulary gate.
---

# Work Order: surface a stranded corrupt cancel lineage as a durable recovery record

> **HUMAN-GATED (event-log truth).** This adds a new *condition* under which the log is
> written: a persistently malformed cancel lineage now mints a durable, deduped
> `needs_review` recovery record instead of only a per-tick log line. The record shape and
> mechanism are **pre-ratified in the kickoff decision block** (D-ML-1..6) — decidable now.
> Because it **reuses** the existing `SUBMIT_RECOVERY_NEEDS_REVIEW` event + `SubmitRecoveryRecord`
> ledger (no new `ExecutionEventType`, no new table, no migration), there is **no** mid-session
> schema/vocabulary gate. It still ends at `status: REVIEW` with `work/review/REV-0040/request.md`
> staged for the **Claude seat** (cross-model rule); no ledger close-out line until dispositioned.

> **NOT a regression fix.** This is pre-existing WO-0036 behavior the WO-0124 review disclosed
> and deferred (REV-0037 P2-1; author disclosure `app/monitoring.py:1499-1501`). No live safety
> invariant is violated today — a corrupt lineage already fails **closed** (no target guessed,
> zero venue calls). This WO only makes the stranded exposure durably operator-visible.

## Goal

At the malformed-lineage fail-closed branch of envelope cancel-convergence
(`app/monitoring.py:1502`), mint **one deduped `RECOVERY_NEEDS_REVIEW` record per corrupt
envelope lineage** through the existing `store.create_submit_recovery(...)` seam — so a
genuinely stranded legacy SELL behind a corrupt lineage reaches the operator through the
recovery ledger (the intended human surface for stranded venue exposure), not only through
lossy per-tick log noise. Replay-exact and dual-store-parity from birth; never auto-cancelled;
resolved only by the operator's HUMAN_ATTESTED reconcile.

## Context packet (read fully before the first commit)

- `work/review/REV-0037/result.md` §"P2-1" (lines 77-88) — the finding in the reviewer's own
  words, and the author's disclosure it cites.
- `app/monitoring.py:1486-1511` — the fail-closed branch (the log-only site, the disclosed
  deferral comment at :1499-1501). `app/monitoring.py:1352-1381` —
  `_escalate_disposition_cancel_exhausted`, the existing NEEDS_REVIEW emitter this WO mirrors
  (but for the *no-valid-child* case, so it cannot pass a concrete order).
- `app/store/base.py:858-913` — the `create_submit_recovery` contract: missing local row is
  valid input; `""` is the supported unknown-broker-id sentinel scoped per local order;
  cardinality one row per `(local_order_id, broker_order_id)`; scope-match on an existing row.
- `app/store/memory.py:4190-4269` — the **idempotency mechanics** this WO depends on:
  `same_pair AND same_scope AND compatible_status` → returns the existing record (no new
  event); a *different* terminal status for the same pair **raises** `RecoveryTransitionError`
  (:4219). This is the source of Hazard 1 and Hazard 2 below.
- `app/models.py:887-912` — `RECOVERY_NEEDS_REVIEW`, `RECOVERY_OPEN_STATUSES`,
  `RECOVERY_OPERATOR_RECONCILED`, and the recovery status-transition graph.
- `docs/adr/ADR-012-submit-recovery-operator-release.md` (**Accepted 2026-07-22**) — the
  `operator_reconciled` terminal + HUMAN_ATTESTED authority that resolves the record.
- `ExecutionEnvelope` model (`app/models.py:672-761`): `symbol`, `side` (locked SELL by
  validator, :755), `qty_ceiling` (immutable), `remaining_quantity` (read-model counter,
  drifts on fills), `sell_intent_id`. The immutable fields are the stable dedupe-scope source.

## The pre-ratified design (D-ML-1..6 — see kickoff; restated here as the contract)

At `app/monitoring.py:1502`, before/instead of the log-only `return`, emit the durable record:

```
lineage_key = f"lineage:{reloaded.id}"          # synthetic — NEVER an order id (Hazard 3)
existing = [
    r for r in await store.list_submit_recoveries()   # statuses=None → ALL, incl. terminal
    if r.local_order_id == lineage_key and r.broker_order_id == ""
]
if not existing:                                 # create exactly once (Hazard 2)
    await store.create_submit_recovery(
        local_order_id=lineage_key,
        broker_order_id="",                      # supported unknown-id sentinel
        client_order_id=reloaded.id,             # STABLE (Hazard 1)
        symbol=reloaded.symbol,                  # STABLE
        side=reloaded.side,                       # STABLE (locked SELL)
        quantity=reloaded.qty_ceiling,           # IMMUTABLE — never remaining_quantity (Hazard 1)
        limit_price=None,                        # STABLE
        failure_reason="envelope_lineage_malformed",   # reason code lives in monitoring.py (Hazard 4)
        session_id=None,                         # STABLE
        candidate_id=None,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
        event_type=EventType.SUBMIT_RECOVERY_NEEDS_REVIEW.value,   # REUSE — no new type
        extra_payload={
            "envelope_id": reloaded.id,
            "malformed_lineage": True,
            "sell_intent_id": reloaded.sell_intent_id,
            "remaining_quantity": reloaded.remaining_quantity,
            "missing_envelope_ids": sorted(projection.missing_envelope_ids),
            "missing_order_ids": sorted(projection.missing_order_ids),
            "invalid_order_ids": sorted(projection.invalid_order_ids),
        },
    )
    # first-detection warning here (optional log-quieting per D-ML-6)
# keep the existing fail-closed return
```

## Required behavior

- [ ] **GATE** (fable_gate in this file's record): confirm the exact reuse contract holds by
      reading the store methods — specifically that a synthetic `local_order_id` with no order
      row + `broker_order_id=""` + `RECOVERY_NEEDS_REVIEW` (a) passes the scope-match guard
      (missing local row is valid input), (b) drives the WO-0132-hardened `claim_occurrence is
      None` path deterministically on **both** stores, and (c) is idempotent per tick. If ANY
      of these does not hold, **STOP and escalate** — the fallback (a new `ExecutionEventType`
      + projector + table) is a larger gated surface and a different WO, not scope to absorb.
- [ ] **Red-first:** a dual-store test that drives a malformed lineage (populate
      `projection.missing_order_ids`/`invalid_order_ids`/`missing_envelope_ids`) through
      convergence and asserts a `RECOVERY_NEEDS_REVIEW` record + `SUBMIT_RECOVERY_NEEDS_REVIEW`
      event appears — RED before the change, GREEN after. Paste both.
- [ ] Emit the record per the pre-ratified design; keep the fail-closed posture (no target
      guessed, zero venue calls) exactly as today.
- [ ] **Idempotent dedup pin:** N (≥3) convergence ticks over the same corrupt lineage produce
      **exactly one** record and **exactly one** event, on **both** stores. This is the core
      REV-0037 P2-1 property ("one deduped needs_review").
- [ ] **Post-reconcile safety pin (Hazard 2):** after the operator reconciles the record to
      `RECOVERY_OPERATOR_RECONCILED`, a subsequent convergence tick over the still-corrupt
      lineage **does NOT raise** and **does NOT re-create** (the pre-check skips it). Both
      stores. (Without the `list_submit_recoveries` pre-check, the re-create would hit
      `create_submit_recovery`'s `compatible_status` guard and raise `RecoveryTransitionError`,
      faulting the tick — this pin is the regression guard for that.)
- [ ] **Scope-stability pin (Hazard 1):** the recorded scope uses only immutable envelope
      fields, so no tick ever triggers the `not same_scope` raise even if `remaining_quantity`
      changes. A test that mutates `remaining_quantity` between ticks and asserts no raise + no
      second record.
- [ ] **Replay / dual-store parity:** replaying the event log reconstructs the same recovery
      read-model in both stores (reuses the existing `SUBMIT_RECOVERY_NEEDS_REVIEW` fold; assert
      via the existing recovery parity path). The `order_id` carried on the event is the
      synthetic `lineage:<id>` key; position projection remains FILL-only (INV-1/INV-9 — the
      needs_review event is structurally invisible to the Position Service).
- [ ] **Operator surface:** the record appears in `list_submit_recoveries(RECOVERY_OPEN_STATUSES)`
      (the operator read surface) and is never returned to the recovery loop's
      `{RECOVERY_UNRESOLVED}` filter, so the loop never auto-polls/auto-cancels it (confirmed by
      status + the empty broker id). Pin it.
- [ ] **(D-ML-6, optional/bounded):** downgrade the per-tick `_log.warning` at :1502 to
      first-detection only (fire when the record is created; stay quiet on subsequent no-op
      ticks) — this is the log-noise remedy the reviewer named. If it complicates the change,
      keep the existing warning and note it; do not expand scope for it.
- [ ] **Stage `work/review/REV-0040/request.md`** for the Claude seat: scope, commit(s), the
      reuse rationale (why no new vocabulary/table), the two hazard pins, and the dual-store +
      replay evidence index.

## War-game — anticipated issues, resolved ahead of time

| # | Hazard | Why it bites | Resolution baked into the design |
|---|---|---|---|
| 1 | **Idempotency raises if a scope field drifts.** `create_submit_recovery` treats a re-create of the same `(local_order_id, broker_order_id)` pair as idempotent **only if `same_scope`** (symbol/side/quantity/limit_price/client_order_id/session_id all equal, memory.py:4203-4218). | `remaining_quantity` decrements on fills; if used as `quantity` it could differ tick-to-tick → `not same_scope` → `RecoveryTransitionError` → faulted convergence tick. | Record only **immutable** envelope values: `quantity=qty_ceiling`, `limit_price=None`, `client_order_id=envelope.id`, `session_id=None`. `remaining_quantity` and the (mutable) ambiguity sets live in `extra_payload`, which does **not** participate in the scope check. Explicit scope-stability pin. |
| 2 | **Re-create after operator reconcile raises.** Once the operator reconciles → `RECOVERY_OPERATOR_RECONCILED` (terminal), the next tick's `create_submit_recovery(..., RECOVERY_NEEDS_REVIEW)` for the same pair has `compatible_status = False` (NEEDS_REVIEW ≠ OPERATOR_RECONCILED and ≠ UNRESOLVED) → raises. | The lineage may stay corrupt after the human took responsibility; a naive per-tick create would fault every tick post-reconcile. | Pre-check `list_submit_recoveries()` (all statuses) for the lineage pair and **skip create if any record exists in any status**. HUMAN_ATTESTED reconcile is final — the WO never re-flags a lineage the operator already dispositioned. Explicit post-reconcile pin. |
| 3 | **Synthetic key collides with a real order id.** `create_submit_recovery` scope-matches against an existing order row when `local_order_id` resolves to one. | Overloading `local_order_id` with an envelope id could (astronomically) collide, or confuse a reader. | Prefix the key: `f"lineage:{envelope.id}"` — structurally not an order id, guaranteed no collision, and it drives the already-hardened (WO-0132) `claim_occurrence is None` path. |
| 4 | **File conflict with WO-0134 (R4).** Both are gated Codex work in the same batch; a new `models.py` constant would share R4's additive `models.py` region. | Serialized-file contention / merge friction. | Keep `failure_reason="envelope_lineage_malformed"` as a **string literal in `app/monitoring.py`** (not a `models.py` constant). WO-0135's footprint is then `app/monitoring.py` + `tests/**` only — **disjoint** from R4's file set; the two lanes need no serialization. |
| 5 | **Reuse turns out unsound.** If the store rejects the synthetic key, or the None-claim path diverges between stores, reuse fails. | A store patch to make it work would be an unapproved gated store-truth change. | `app/store/**`, `app/models.py`, `app/events/**` are **forbidden paths**. Reuse-or-escalate: an unsound reuse is a STOP-and-escalate finding (fallback = a separate, larger WO with a real vocabulary/schema gate), never a silent store edit. |
| 6 | **Log spam vs durability.** Reviewer wants the quieter, fuller remedy without losing the alert. | Removing the warning could hide a fault; keeping per-tick spam is what was flagged. | D-ML-6: warn on first detection (record creation) only; the durable record carries the persistence. Bounded/optional so it never balloons scope. |

## Allowed paths

```yaml
allowed_paths:
  - app/monitoring.py                 # the :1502 escalation call site + first-detection warn
  - tests/**                          # dual-store + idempotency + post-reconcile + scope-stability pins
  - docs/INVARIANTS.md                # cross-ref ONLY if a lineage-visibility invariant is apt
  - work/active/**                    # WO activation + state scoreboard row
  - work/review/REV-0040/             # request.md staging
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**                      # reuse create_submit_recovery AS-IS; a store change = STOP/escalate
  - app/models.py                     # no new constant/type (stay disjoint from R4); reason code is a monitoring.py literal
  - app/events/**                     # reuse the existing SUBMIT_RECOVERY_NEEDS_REVIEW fold; no projector change
  - app/facade/**                     # operator surface already reads RECOVERY_OPEN_STATUSES
  - cockpit/**
  - app/api/**
  - docs/adr/**                       # ADR-012 consumed, not edited
  - docs/spec/**
  - work/ledger.jsonl                 # ends at REVIEW; no close-out line in-session
  # (all signal-seat / R4 files — that is WO-0134's lane)
```

## Acceptance criteria

- [ ] Malformed lineage mints exactly one `RECOVERY_NEEDS_REVIEW` record + one
      `SUBMIT_RECOVERY_NEEDS_REVIEW` event, deduped across N ticks, on both stores (evidence).
- [ ] Post-reconcile tick does not raise and does not re-create (both stores).
- [ ] Scope-stability holds under a `remaining_quantity` change (no raise, no second record).
- [ ] Fail-closed posture unchanged: zero venue calls, no target guessed on the corrupt path.
- [ ] Replay reconstructs the record identically; recovery loop never auto-acts on it.
- [ ] Full gates green: `ruff check .`, `ruff format --check .`, `mypy app/`, `lint-imports`,
      `pytest -q` (OS-temp basetemp), `python tests/r2_conformance_oracle.py`,
      `pytest -q tests/test_wo0113_repair_scaling.py`. Fresh pasted output each.
- [ ] `status: REVIEW`, WO in `work/active/`, REV-0040 staged, branch pushed, nothing merged,
      no ledger line. Fable record (gate + FIX blocks + evidence) appended to this file.

## Stop conditions

- Reuse of `create_submit_recovery` proves unsound (scope guard, None-claim divergence, or
  idempotency) → STOP and escalate; do NOT patch `app/store/**` or add a new event type.
- Enforcing durability would change the fail-closed decision (i.e. cause any venue call or a
  guessed target) → STOP; that would be a safety regression, not this WO.
- Any conflict between the finding, ADR-012, and code on the recovery surface → record the
  decision gap (CLAUDE.md conflict rule); never silently pick.
- Never weaken an existing recovery/convergence test.

## Completion disposition (post-review, not in-session)

Expected at eventual close-out: `[RESULT_SUMMARY_KEPT]` (+ `PKL_UPDATED` if a recovery-surface
PKL page states the log-only behavior). The close-out commit (after REV-0040 ACCEPT /
ACCEPT-WITH-CHANGES) ships status flip + disposition + ledger line + file move to
`work/completed/keep/`, and flips the REV-0037 P2-1 advisory line in
`work/queue/REVIEW-REMEDIATION-BATCH.md` to resolved-by-WO-0135.
