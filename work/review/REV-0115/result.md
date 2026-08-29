# REV-0115 — Independent Review Result

Review target: `25aca36956d68db014df3769678699597e9be56a..7c0e52b26cf0bc1b82bbfa04ffc4131e80161145`

Review was read-only. No SQLite/database was opened or created; no DDL, configured path, or `tests_gated`/held suite was executed.

### P0 — Unbound manual-flatten state authorizes SELL effect creation

- Location: `app/execution_core/authority.py:8154`; `app/execution_core/persistence/checkpoint_codec.py:4284`; `app/execution_core/persistence/unit_of_work.py:2756`
- Evidence: `reproduced-live` using a pure non-DB counterexample. Two states had identical authenticated manual projections; adding only an unbound `READY` row to `_manual_by_id` changed the same `CreateBrokerEffect` from `REFUSED / MANUAL_FLATTEN_INVALID` to `APPLIED`, creating `uow-omitted-ready-sell-effect`.
- Impact: omitted mutable state can exercise the human-gated manual-flatten authority and create broker intent without an authenticated active-scope binding.
- Required root resolution: derive exact operation-keyed manual proof for `CreateBrokerEffect`, require the active scope binding, and make the reducer consume that proof instead of raw `_manual_by_id`. Add payload-equal pure and UOW counterexamples.

### P0 — Route-less canonical corrections and busts are rejected

- Location: `app/execution_core/persistence/unit_of_work.py:5019`; `tests/execution_core/test_persistence_unit_of_work.py:826`
- Evidence: `reproduced-live` for `BrokerTradeCorrectFact`; `static-reasoning` for the shared `BrokerTradeBustFact` guard. The existing fixture admits an unowned first fill as `APPLIED` with no route. A valid predecessor-linked correction with that route absent raised `_TechnicalRefusal: broker revision proof is incomplete`.
- Impact: broker-authoritative corrections or busts following a quarantined unmatched fill cannot update its economics or quantity, leaving stale execution truth.
- Required root resolution: separate broker-truth acceptance from attribution. Persist predecessor-valid route-less revisions through O1, update the quarantined successor state, and retain reconciliation-required status without inventing ownership. Add fill→correct and fill→bust replay/conflict tests.

### P1 — Mandatory O1–O8 ordered-write ratchet and fault controls are absent

- Location: `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:300`; `app/execution_core/persistence/unit_of_work.py:5273`; `tests/execution_core/test_persistence_unit_of_work.py:1279`
- Evidence: `static-reasoning`. Frozen-contract lines 314–321 define O1–O8 write order; lines 329–332 require a row-specific exact-call table and a ratchet rejecting missing, extra, reordered, dynamically selected, or wildcard calls. No equivalent table or failure-capable ratchet exists, and per-write before/after fault coverage is incomplete.
- Impact: atomic write families can be omitted or reordered without causing the contract suite to fail; the route-less O1 defects escaped this gap.
- Required root resolution: add the exact O1–O8 repository-call table and ratchet, including all mandated negative mutants, plus before/after fault assertions for each semantic family, checkpoint, receipt, outcome, and outbox boundary.

Verdict: BLOCK
P0: 2
P1: 1
P2: 0
Unverified: executable SQLite/DDL agreement; configured-path behavior; held tests_gated results; end-to-end database crash/restart and per-write fault behavior for O1–O8
