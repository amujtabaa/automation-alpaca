---
type: Work Order
title: "PD-1: needs_review reconciliation release valve (human-gated, event-truth)"
status: REVIEW
work_order_id: WO-0114
wave: post-R2 beta-prep
model_tier: strong
risk: high
disposition: []
owner: Ameen (ratifies) / planning seat drafted 2026-07-20 / Codex implementer seat
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

- [x] **Vocabulary (per D-PD1-2):** one NEW terminal cleanup status (candidate names in the
      decision register; never reopen to `unresolved`), added to `RECOVERY_STATUSES` /
      `RECOVERY_TRANSITIONS` (`needs_review → <new>` is the only new edge) and
      `recovery_status_event`; a distinct audit `EventType` (e.g. `submit_recovery_reconciled`).
      The recovery loop still selects only `{RECOVERY_UNRESOLVED}` (monitoring.py:2869) and can
      never touch the record again. No SQLite DDL is required (`cleanup_status` is unconstrained
      TEXT, sqlite.py:353-369) — state so in the ADR, don't invent a migration.
- [x] **Attestation contract:** the command carries actor, non-empty reason, evidence reference,
      and a full identity echo — `recovery_id`, `local_order_id`, `broker_order_id`
      (`client_order_id` when the row has one), `symbol`, `side` — plus the attested facts:
      broker-terminal state and cumulative venue filled quantity for that exact broker order.
      Any mismatch with the durable row fails closed with zero writes.
- [x] **Fail-closed contradictions:** non-terminal attested broker state; malformed/incomplete
      evidence; identity mismatch (wrong recovery/order/broker-id/symbol/side, or
      envelope/owner lineage that no longer matches the projection); cumulative-fill parity
      failure — attested cumulative quantity ≠ the sum of canonical FILL events for that
      `(local_order_id, broker_order_id)` in event truth (zero-fill terminal evidence must match
      zero canonical fills); record not in `needs_review` (see idempotency below).
- [x] **Truth rule:** the transition writes NO fill and moves NO position. Discovered fills enter
      truth only as canonical deduplicated FILL events (`plan_append_fill`, dedupe
      `fill:{order_id}:{source_fill_id}`) with honest provenance per D-PD1-1/D-PD1-4 — via a
      SEPARATE ingestion command if D-PD1-4 ratifies the recommended split. Parity is checked
      against event truth at valve time, so ingestion (which legitimately moves position) always
      precedes release, and the un-released interval stays quarantined (safe).
- [x] **Atomic revalidation:** all checks + status write + audit `Event` (payload
      `{actor, reason, evidence_ref, attested facts}`) + `ExecutionEvent` (provenance per
      D-PD1-1) happen in ONE store-lock/transaction hold, following the
      `_write_emergency_reduce_override_locked` template (sqlite.py:7253-7285). There is no CAS
      token on recovery rows (base.py:936-943) — the lock-serialized read-validate-write IS the
      concurrency mechanism; a concurrent transition loses cleanly (`RecoveryTransitionError`
      surfaces, zero partial writes).
- [x] **Idempotency:** an exact repeat of an already-applied attestation returns success with no
      new writes; a DIFFERENT attestation against an already-released record is a 409-class
      refusal. Replay/restart never double-applies (SQLite reopen parity).
- [x] **Projection contribution removal:** the released record leaves
      `needs_review_child_order_ids` (core.py:1780-1800), `_order_needs_review_*`
      (memory.py:948 / sqlite.py:1829), and every `RECOVERY_OPEN_STATUSES` scan. Release lifts
      the symbol's sell side ONLY if no other predicate holds — another open recovery, strict
      retention, malformed-ambiguity, venue obligation, TIMEOUT_QUARANTINE, or the ADR-001
      overfill latch (which is permanent and is NOT touched by this WO) each independently keep
      the quarantine.
- [x] **Boundary:** operators and the cockpit reach this only through the typed facade
      command + `POST` route (`Depends(get_command_facade)`, `X-Actor`, `FacadeError` → 404/409/422
      mapping). The D-PD1-3 cockpit control calls the typed API client only — no route→store,
      no route→broker, no UI-owned state; an AppTest pin proves the button renders
      server-classified outcomes and imports no store/broker module.
- [x] **Docs ship with the change:** new ADR-012 (valve semantics + decisions as ratified),
      ADR-008 amendment iff vocabulary added, INV-096, `pkl/safety/invariants-rationale.md`,
      and the hardening gates (`tests/test_review_hardening_gates.py` enum-total/producer-consumer)
      extended to the new status + consumers.

## Required tests

All red-first, BOTH stores, SQLite reopen/restart parity where marked (R):

- [x] Denial without evidence/actor/reason; malformed evidence; non-terminal broker state.
- [x] Wrong identity: recovery id, local order, broker id, symbol, side, envelope/owner lineage.
- [x] Cumulative parity: zero-fill terminal, partial fills, fully accounted fills, contradiction
      (attested ≠ event truth) — each refused/accepted correctly. (R)
- [x] Discovered-fill path (per D-PD1-4): canonical dedupe under retry AND replay — one FILL,
      one position movement, never two. (R)
- [x] Valve never moves position: position projection byte-identical before/after a successful
      release with fully-accounted fills. (R)
- [x] Concurrency: valve vs concurrent monitoring/recovery tick; interleaved double-submit —
      exactly one applies, loser fails closed with zero partial writes.
- [x] Idempotent repeat (same attestation) and 409 on conflicting re-attestation. (R)
- [x] Contribution-only release: second open recovery (or malformed obligation) on the same
      symbol keeps stage/claim/direct-SELL/flatten quarantine; release of the LAST predicate
      lifts them (assert via the existing WO-0108/0109 rails, not new path-local checks). (R)
- [x] ADR-001 latch survives a release (permanent-latch contract intact).
- [x] Zero venue calls: adapter spy proves no submit/cancel/replace from the valve path.
- [x] Audit/provenance: actor/reason/evidence durably visible; open-recoveries operator view
      drops the record; full record remains queryable. (R)
- [x] Existing pins updated ONLY where the old "terminal forever" claim legitimately changed
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

- [x] All required behavior implemented per the RATIFIED D-PD1-1..4 (no improvised semantics).
- [x] Tests above green both stores + restart; mutation checks on the parity and identity rails.
- [x] Scope limited to allowed paths; no forbidden paths touched.
- [x] Fable FULL gate + DONE block with fresh pasted evidence.
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

## Fable FULL implementation record

```yaml
fable_gate:
  goal: "Release exactly one needs_review submit-recovery contribution after evidenced venue/event-truth parity, without manufacturing a fill."
  assumptions:
    - "D-PD1-1..4 in the operator decision block are the complete authority for this gated surface."
    - "The recovery row's durable order and append-only claim/event history are the identity source; cockpit echoes never authorize a write."
    - "Alpaca Paper only; no credential or venue call is required."
  approach: "Add one terminal attestation-only edge, a separate canonical human-fill command, atomic dual-store implementations, typed facade/API/cockpit boundaries, and occurrence-scoped projection consumers."
  out_of_scope:
    - "ADR-001 latch release, TIMEOUT_QUARANTINE release, broker automation, schema migration, live trading, or reconciliation-loop relaxation."
    - "Out-of-scope primer cleanup at docs/00_START_HERE.md:394 and :840."
  done_when:
    - "Both stores and SQLite reopen prove identity, parity, replay, concurrency, contribution-only release, and position neutrality."
    - "Typed API/cockpit and producer-consumer hardening gates are green."
    - "ADR-012/ADR-008/INV-096/PKL are staged and REV-0035 awaits an independent seat."
  blast_radius: "One human-gated paper-trading recovery record and its exact submission-claim occurrence; no venue call."
```

### RED evidence

```yaml
evidence:
  command: "pytest -q tests/test_wo0114_pd1_release_valve.py (red checkpoint b6d4fb0)"
  result: FAIL
  decisive_output: "Collection failed: ImportError for RECOVERY_OPERATOR_RECONCILED; production vocabulary/commands did not exist."
```

```yaml
evidence:
  command: "pytest -q tests/test_wo0114_pd1_release_valve.py -k 'filled_attestation_cannot_be_partial or recovery_without_durable_claim_occurrence_fails_closed'"
  result: FAIL
  decisive_output: "4 failed: both stores accepted partial FILLED evidence and a recovery with no durable claim occurrence."
```

### FIX records

```yaml
fable_fix:
  symptom: "An envelope stayed paused after its last needs_review recovery was released."
  root_cause: "The new non-broker release fact changed recovery openness but was not yet a lifecycle consumer, so the exact claim/venue interval stayed open in direct-SELL and envelope projections."
  evidence: "The end-to-end next-stage test failed after a successful status transition."
  fix: "Persist claim_occurrence on the evidence payload and consume SUBMIT_RECOVERY_OPERATOR_RECONCILED in both shared lifecycle projections, closing only that occurrence."
  regression_test: "test_envelope_fill_and_release_preserve_lineage_and_apply_once; test_direct_sell_recovery_blocks_fresh_owner_until_release"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The first full suite had one failure in test_interface_has_no_fill_mutators."
  root_cause: "The interface-totality pin enumerated the pre-WO fill-named API and did not classify the ratified evidence-bearing command boundary."
  evidence: "1 failed at 20 percent; extra StateStore member ingest_submit_recovery_fill."
  fix: "Classify the command explicitly and add a structural assertion that both stores delegate to append_fill/record_envelope_fill with no direct fills-table writer."
  regression_test: "tests/test_fills_append_only.py (4 passed), followed by full-suite exit 0"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The review-stage branch passed plain pytest but failed the repository's 93 percent CI-form branch-coverage gate."
  root_cause: "The original full-suite command omitted --cov=app --cov-branch, so the review evidence could not expose thin negative-path coverage in the new human-gated surface."
  evidence: "The inherited 27e82bc coverage artifact measured 15,320 / 16,555 combined statement-plus-branch units (92.540018 percent), below fail_under=93."
  fix: "Add failure-capable HTTP, facade, lineage, dual-store corruption/state, pure-defense, exact-replay, and SQLite-reopen cases without weakening an existing assertion."
  regression_test: "tests/test_wo0114_pd1_release_valve.py; exact semantic head measures 15,411 / 16,548 units (93.129079 percent)."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "After two fills advanced one broker leg from cumulative 4 to 6, an exact retry of the older cumulative-4 command was rejected instead of returning a write-free duplicate."
  root_cause: "The exact-replay branch compared the historical command cumulative value with the latest canonical broker-leg total before the stores compared the durable event and fill identity."
  evidence: "Reintroducing the comparison failed exactly three public-command nodes: memory, SQLite, and SQLite reopen."
  fix: "Skip latest-total parity only for a dedupe-key replay; retain intrinsic/capacity validation and require the stores' durable event payload plus complete fill-row economics/source/session identity before duplicate success."
  regression_test: "test_older_fill_exact_retry_remains_write_free_after_later_fill; test_older_fill_exact_retry_remains_write_free_after_sqlite_reopen"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "A corrupted compatibility fill row with AAPL event truth but MSFT row truth was returned as an exact duplicate."
  root_cause: "Both store replay checks compared only fill quantity, price, and side; symbol/order/source/session identity were omitted. A coverage setup also created an orphan FILL event instead of canonical row/event truth."
  evidence: "The new corruption control failed exactly twice before the repair (memory and SQLite); the corrected 17-node replay/state slice passed."
  fix: "Centralize full recovery fill-row identity comparison, apply it in both stores, and replace the orphan-event setup with append_fill plus row/position assertions."
  regression_test: "test_exact_replay_rejects_corrupt_fill_read_model; test_recovery_command_state_guards_are_dual_store_and_write_free"
  red_green_verified: true
  attempt: 1
```

### Fresh evidence

| Classification | Command | Decisive output |
|---|---|---|
| VERIFIED | `ruff check .` | `All checks passed!` |
| VERIFIED | `ruff format --check <all WO-0114 Python paths>` | all scoped files already formatted |
| BLOCKED | `ruff format --check .` | six pre-existing/out-of-lane files would reformat: three `app/recorder/` files, `harness/bootstrap.py`, `tests/test_tape_recorder.py`, and reviewer-owned `work/review/AUDIT-0002-priorwork/probe_review_integrity.py`; no WO-0114 edit made |
| VERIFIED | `mypy app/` | `Success: no issues found in 70 source files` |
| VERIFIED | `lint-imports` | `Contracts: 6 kept, 0 broken` |
| VERIFIED | `pytest -q tests/test_wo0114_pd1_release_valve.py tests/test_wo0114_cockpit_release.py tests/test_review_hardening_gates.py` | 121 passed (104 store/API + 3 cockpit + 14 hardening) |
| VERIFIED | parity guard mutation | 2 failed only at cumulative parity (memory + SQLite); restored 22/22 green |
| VERIFIED | echoed-symbol guard mutation | 2 failed only at symbol identity (memory + SQLite); restored 22/22 green |
| VERIFIED | older-fill latest-total mutation | 3 failed only at older exact replay (memory + SQLite + SQLite reopen); restored 3/3 green |
| VERIFIED | replay event-evidence mutation | 3 failed only at conflicting replay evidence (memory + SQLite + SQLite reopen); restored 3/3 green |
| VERIFIED | fill-row symbol corruption RED/GREEN | 2 failed before complete row-identity comparison; corrected replay/state slice 17/17 green |
| VERIFIED | `pytest -q tests/r2_conformance_oracle.py tests/test_r2_conformance_oracle_claude.py` | 83 passed, 6 skipped, exit 0 |
| VERIFIED | `pytest -q tests/test_review_hardening_gates.py` | 14 passed, exit 0 |
| VERIFIED | CI-form `pytest -q --cov=app --cov-branch` on the semantic tree integrated as `ffd818b` | 4,003 passed, 11 skipped, 1 xfailed; required 93.0 reached; 93.129079% (15,411 / 16,548 units); exit 0; 400.86 s |
| VERIFIED | `git diff --check` | exit 0 |

```yaml
fable_done:
  task: "WO-0114 PD-1 needs_review release valve implementation stage"
  done_when_results:
    - "VERIFIED: ratified dual-command semantics implemented with no broker calls or schema change."
    - "VERIFIED: both stores, SQLite reopen, typed boundary, cockpit, projection rails, and mutations pass."
    - "VERIFIED: ADR-012 is Proposed and REV-0035 is staged; beta reliance remains gated."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Exact semantic tree integrated as ffd818b: full CI-form suite 4,003 passed / 11 skipped / 1 xfailed; 93.129079 percent branch-aware combined coverage; exit 0."
    - "Conformance 83 passed / 6 skipped; hardening 14 passed."
    - "Ruff check, mypy, import-linter, scoped Ruff format, and diff check green."
  status: VERIFIED
```

## Integration NEEDS-INPUT (does not reopen this implementation lane)

- `docs/00_START_HERE.md:394` still describes three recovery values and
  `unresolved -> {resolved, needs_review}` with both outcomes terminal. Required replacement:
  four values; `unresolved -> {resolved_canceled, needs_review}` and the sole human-gated
  `needs_review -> operator_reconciled` edge; every resolved state remains terminal and generic
  recovery updates cannot take the human edge.
- `docs/00_START_HERE.md:840` says a `needs_review` record stays open until a human clears it but
  does not name the truth contract. Required replacement: it remains open until the separate fill
  command has recorded every canonical execution and an exact full-identity, terminal-state,
  cumulative-parity attestation transitions that one record to `operator_reconciled`; the recovery
  driver still acts only on `unresolved`.
- Repository-wide `ruff format --check .` remains blocked by six pre-existing/out-of-lane files:
  `app/recorder/__init__.py`, `app/recorder/models.py`, `app/recorder/store.py`,
  `harness/bootstrap.py`, `tests/test_tape_recorder.py`, and the reviewer-owned AUDIT-0002 probe.
  The WO-scoped format gate is green; do not absorb those files into this lane.
- ADR-012 human acceptance and REV-0035 `ACCEPT` / `ACCEPT-WITH-CHANGES` remain mandatory before
  beta reliance. No disposition, ledger close, or work-order move is authorized yet.

## Completion disposition

Complete after merge/closure per template; expected: `[ADR_CREATED, PKL_UPDATED,
RESULT_SUMMARY_KEPT]`.
