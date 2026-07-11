# WO-0017 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0017]` — closed 2026-07-11, commit `bce10f0` on `feat/execution-envelope-wo-0017`. Gated surfaces (kill switch, manual flatten, order-submission delegation); T2 approval granted in-chat by Ameen after the posted gate block + diff surface.

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| create→approve→ACTIVE one store-atomic unit; kill mid-flow ⇒ zero artifacts, both stores | ✅ | `test_halted_blocks_approval_with_zero_artifacts` (REV-0020 mirror) + `test_kill_race_never_ends_with_an_active_envelope_under_halted` (gather race, both orderings consistent). **Mutation-checked:** disabling the sqlite HALTED check fails the zero-artifact test |
| Approval idempotent per gate conventions | ✅ | re-approve of ACTIVE = no-op with NO new events; pre-existing PENDING draft completes the chain; terminal ⇒ `EnvelopeTransitionError`; concurrent same-draft approvals yield ONE trail; concurrent different-draft approvals single-flight per intent |
| Approval events carry operator-* provenance | ✅ | CREATED + APPROVED payload actor == "operator-ameen"; autonomous events (kill-freeze, fills) stay engine/system actor |
| Kill ⇒ every ACTIVE envelope FROZEN before further envelope action; explicit-human resume | ✅ | `test_kill_freezes_every_active_envelope_atomically` (multi-symbol, PENDING untouched, reason=kill_switch), `test_release_never_auto_resumes`, `test_resume_and_activation_are_refused_while_halted` (OrderIntentBlockedError; CANCELLED still allowed) |
| Flatten cancels/freezes symbol envelopes FIRST, same atomic unit; ADR-003 deferral unchanged | ✅ | preemption on create + already-flat outcomes (ACTIVE via FROZEN→CANCELLED, PENDING/FROZEN too; other symbols untouched; FROZEN-before-CANCELLED ordering asserted); deferral to a live protection exit leaves its envelope ACTIVE; `tests/test_phase7_flatten_atomic.py` green with a ZERO-line diff |
| Dispositions mandatory at approval time | ✅ | structurally unconstructible without them (ValidationError) + tampered-draft rejection |
| Full gate | ✅ | ruff check ✓ · format --check (207 files) ✓ · mypy 64 files ✓ · lint-imports 6 kept ✓ · pytest full suite exit 0, 0 failures |

## Scope check

Touched: `app/store/memory.py`, `app/store/sqlite.py` (approve op, kill hook, flatten hooks, HALTED gate on →ACTIVE), `app/approval/envelope.py` (new gate), `tests/test_wo0017_*.py` (2 new files), `docs/INVARIANTS.md` (INV-080/081). All inside allowed paths.

## Visible deviations from the posted gate block

- `[FABLE DEVIATION]` facade/`routes_trading.py` thin wiring NOT implemented — deferred to WO-0020 where the cockpit consumer lands. No behavior in this WO's done_when needed it; adding an unconsumed HTTP surface to a gated flow would have widened the diff for nothing (Law 4). `app/models.py` also untouched (no approval-context field proved necessary, as predicted).
- `EnvelopeApprovalGate` typed against a local structural `Protocol` because `app/store/base.py` is outside scope; WO-0019 lifts the envelope API into the `StateStore` ABC (already in the deferred log).

## Incident note

One toolchain slip during the mutation check: a reflexive `git checkout app/store/sqlite.py` reverted the uncommitted WO changes; they were re-applied from the identical scripted patch and the full test run re-verified (37/37 both stores). No committed state was ever affected.

## Status: VERIFIED
