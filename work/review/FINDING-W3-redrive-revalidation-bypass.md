# FINDING — redrive is a validation-free venue path; WO-0024's status guard does not close it

- **Status:** OPEN (REV-0022 Phase A; found INDEPENDENTLY by interleaving-attacker INT-001,
  spec-attacker SPEC-03, completeness-critic CC-03 — 3/4 critics, distinct repros, both stores).
- **Severity:** **P1** (H1/H5/H6; oversized and post-TTL venue submissions reproduced from the
  production tick path).
- **Cluster:** F3 in `work/review/REV-0022/phase-a.md`.

## What

`redrive_staged_envelope_action` (app/reconciliation.py:617-652) reads the last ENVELOPE_ACTION
event and the order row, then `_drive_staged_order` re-checks only session controls via the
submission claim. It never re-reads the envelope, never re-runs `validate_action`, and runs FIRST
in `_run_one_envelope` (app/monitoring.py:657-667) — before decide()'s TTL, session-phase, and
stale/bad-data gates. Reproduced consequences (each on both stores):

1. **Oversized submit after a raced fill** (INT-001): fill lands between a transient-failure
   staging and the next tick's redrive → envelope ACTIVE, remaining=40, redrive submits the staged
   80-share order. REPRICE variant *raises* the resting venue order's quantity above remaining.
2. **Venue submit after TTL** (SPEC-03): staged pre-TTL, redriven post-`expires_at`; envelope
   still ACTIVE at submit time. Same shape for out-of-phase redrive (staged 15:59, driven 16:00+).
3. **Restart-redrive on zero market data** (CC-03): a staged CREATED order survives restart; first
   tick redrives it with an empty `EnvelopeTapeBuffer` — a venue submit driven by no data, while
   the policy itself would have said INSUFFICIENT_DATA for ~8 minutes.
4. **Freeze→resume stretches the stage-to-drive gap arbitrarily**, staleness compounding.

**WO-0024 as originally drafted does not fix any of these:** its guard is "refuse unless ACTIVE",
and the envelope is ACTIVE in every repro above. TTL and session-phase are also absent from
`validate_action` itself (app/sellside/policy.py:123-161) — "bounds checked twice" (ADR-009 §1)
is currently untrue for two of the §2 hard rails even on the fresh path.

## Why

The redrive leg was designed to avoid budget double-spend (deliberately skipping re-staging), and
in skipping the *accounting* it also skipped the *rails*. The fresh-staging path catches exactly
these cases (pinned); redrive is the bypass.

## What resolves it

WO-0024 (AMENDED draft): in addition to the non-ACTIVE refusal, redrive re-runs full write-time
validation against current envelope state and current time — rails via `validate_action`
(extended with TTL + phase), plus refusal when staged qty > remaining — before the claim; refusal
locally cancels the staged order with provenance. Strict pins for all four repro shapes, both
stores.

## Repros

Interleaving probe suite (session scratchpad `test_w3_interleaving_probes.py`, re-confirmed on a
pristine `f092ca7` worktree); spec-attacker harness R2; completeness-critic path analysis with
quoted code. Decisive outputs quoted in the critic reports compiled under REV-0022.
