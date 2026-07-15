---
type: Work Order
title: Make a deferred manual-flatten operator-visible + thread the command actor (REV-0002 F-001/F-002)
status: CLOSED
work_order_id: WO-0015
wave: W1
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen (human-gated: manual-flatten)
created: 2026-07-09
---

# Work Order: Make a deferred manual-flatten operator-visible + thread the command actor

## Goal

When a manual flatten is safely deferred to an in-flight protection order
(`CANCEL_PENDING`/`TIMEOUT_QUARANTINE`/`SUBMITTED`), tell the operator plainly that **no
manual order was submitted** (instead of reporting "flatten submitted"), and record
**who** issued the command in the `manual_flatten_deferred` audit event — without
changing the safe no-blind-cancel decision itself.

## Context packet

Read only these first:

- `AGENTS.md`
- `work/review/REV-0002/result.md` (F-001, F-002)
- `app/store/core.py` — `plan_flatten_position` deferral branch (~1027-1065); the `manual_flatten_deferred` `EventSpec`
- `app/facade/store_backed.py` — `create_exit` (~789-826); note it discards `result.outcome`
- `app/api/routes_trading.py` — the flatten route (~90-110); it already resolves `actor`
- `cockpit/app.py` — the flatten call site (~381-383) that reports "flatten submitted"
- `app/models.py` — `FlattenResponse`, `FlattenResult`, `FLATTEN_*` outcomes
- `docs/INVARIANTS.md` — INV-034 / INV-036 (~212, the recorded actor-provenance gap)
- `tests/test_phase7_flatten_atomic.py` (deferral test covers only `SUBMITTED`)

## Allowed paths

```yaml
allowed_paths:
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/api/routes_trading.py
  - cockpit/app.py
  - app/models.py
  - docs/INVARIANTS.md
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**
  - app/marketdata/**
  - app/events/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] **F-001 — deferral is an explicit, operator-visible state.** A deferred flatten no
      longer returns the same success payload as a submitted exit. The response carries
      the deferred order status + a "no manual order submitted; monitoring the existing
      protection exit" signal (see Notes — **human decision D-2** for the exact shape),
      and the cockpit renders it distinctly from "flatten submitted". The safe
      no-second-order behavior is preserved exactly.
- [ ] **F-002 — thread the command actor.** `create_exit(actor=...)` passes the actor
      through `flatten_position` so the `manual_flatten_deferred` event payload records
      it (and, for parity, the created `MANUAL_FLATTEN` intent path where the same actor
      boundary applies). Update the INV-034 note that currently records this as an open gap.

## Required tests

- [ ] Deferral distinctness (memory + sqlite + facade) for `SUBMITTED`, `CANCEL_PENDING`,
      and `TIMEOUT_QUARANTINE`: the response/outcome is distinguishable from a submitted flatten.
- [ ] Actor retained (dual-store + facade): the real `X-Actor` appears in the audit event
      for BOTH the created-flatten and deferred-flatten paths.
- [ ] Cockpit renders the deferred state distinctly (unit-level assertion on the message/branch).
- [ ] RED→GREEN; the existing `SUBMITTED`-only deferral test is extended, not weakened.

## Required commands

```bash
python -m pytest -q tests/test_phase7_flatten_atomic.py tests/test_lifecycle_state_machine.py
python -m pytest -q
ruff check app/ && ruff format --check app/
mypy app/
```

## Acceptance criteria

- [ ] Operator can tell a deferred flatten from a submitted one, in API and cockpit.
- [ ] Actor recorded on created + deferred flatten audit events.
- [ ] No change to the flatten decision, position/order/fill state, or the no-blind-cancel rule.
- [ ] RED→GREEN; no test weakened; scope within allowed paths.
- [ ] Fable DONE block with fresh evidence; INVARIANTS note updated.

## Model-tier rationale

**strong** — manual-flatten is human-gated and the change spans store → facade → api →
cockpit; getting the response contract + the "no state change" guarantee right needs care.

## Notes

- **Human decision D-2 — deferred response shape:**
  - **(A) Explicit field (recommended).** Add an `outcome`/`deferred` discriminator to
    `FlattenResponse` (carrying the deferred order status + next-action hint). Cleanest,
    self-describing to API clients and the cockpit; small additive contract change.
  - **(B) Message-only.** Leave the response shape and derive a distinct cockpit message
    from existing fields. Smaller, but API clients still can't distinguish the two outcomes.
- **Human-gated surface:** manual-flatten. No auto-apply; GATE the approach (esp. the
  response-contract change) before coding.
- Additive-provenance discipline: the `manual_flatten_deferred` event and actor threading
  must not alter any order/fill/position state (INV-9 / single-writer).

## Fable DONE (2026-07-09, commit `a7b012d`)

**Human decision D-2 = Explicit response field (approved).**

**F-001 — deferral is operator-visible.** `FlattenResult.deferred` /
`FlattenResponse.deferred` + `deferred_order_status`, set from `plan.deferral_event is not
None` (NOT the ambiguous `FLATTEN_EXISTING` outcome, so an idempotent own-manual-flatten —
even one at a live SUBMITTED status — stays `deferred=False`). `create_exit` and
`emergency_reduce_override` map it; the cockpit renders a distinct "no manual order
submitted — already exiting; monitoring" toast (`_do` accepts a message callable).

**F-002 — actor recorded.** The command actor threads route→facade→`flatten_position`→
`plan_flatten_position` (pure pass-through) onto the `manual_flatten_deferred` payload and
into `_insert_sell_intent_*` onto the created manual-flatten's `sell_intent_created`
payload; both stores; defaults `COMMAND_ACTOR_SYSTEM`; protection-tick create stays
`"system"`. `docs/INVARIANTS.md` INV-034/036 follow-ups flipped to Resolved.

**Additive-only (INV-9).** Adversarially confirmed byte-identical flatten decision,
no-blind-cancel branch, and order/fill/position state vs. pre-remediation (`git show HEAD~1`);
only defaulted response fields + payload keys + cockpit toast added.

**Evidence:** dual-store + facade + cockpit RED→GREEN parametrized over SUBMITTED /
CANCEL_PENDING / TIMEOUT_QUARANTINE; full suite green; `ruff`/`mypy`/`import-linter` clean.
Adversarial re-verify `wf_eb46fdce-662` (VER-15a/15b) all PASS; no test weakened.

## Completion disposition
- [x] RESULT_SUMMARY_KEPT — this DONE block + `work/review/REV-0002/disposition.md`
  (F-001/F-002) + the INVARIANTS update.

## Distillation checklist
- [x] Ledger updated. INVARIANTS INV-034/036 follow-ups resolved (no new ADR needed).
- [x] Independent review PASSED — **gate CLEARED** (REV-0003, Codex ACCEPT for WO-0015).

## Deletion decision
Keep until REV-0003 dispositions the manual-flatten re-review; then archivable.
