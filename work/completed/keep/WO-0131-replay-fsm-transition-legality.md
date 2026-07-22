---
type: Work Order
title: "Envelope replay must fail closed on FSM-illegal lifecycle transitions"
status: CLOSED
work_order_id: WO-0131
wave: ultra-batch remediation (post-review)
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen / implementer: Codex remediation session
created: 2026-07-21
gated_surface: event-log-truth (replay/read-model interpretation) — human-gated; needs its own review
---

# Work Order: the replay projector's own contract — fail closed on impossible history

> **CLOSE-OUT (2026-07-22).** Replay now fails closed on FSM-illegal transitions (90-pair
> matrix, both replay paths). Independently reviewed: **REV-0038 ACCEPT-WITH-CHANGES →
> RESOLVED** — F1 payload-guard pins landed (`edc8998`) and the surviving mutant re-verified
> killed at `57fcf3f`.

> **HUMAN-GATED (event-log truth).** This changes how corrupted/synthetic event history is
> interpreted at replay. It ends its session at `status: REVIEW` with a fresh packet
> (REV-0038) staged for the Claude seat; the fix is not relied upon until dispositioned.

## Goal

Make the WO-0125 envelope-replay projector actually enforce its stated contract — "a
contradictory lifecycle edge fails closed" — by validating each transition against the
canonical `ENVELOPE_TRANSITIONS` graph, not merely `from == current` and `to == event_type`.

## Context packet

- Codex batch self-review P1-2 + the planning seat's reproduction (a synthetic `PENDING →
  COMPLETED` event is currently ACCEPTED and projected)
- `work/review/AUDIT-0002-priorwork/report.md` (finding-report conventions)
- `app/events/projectors.py` (the `_ENVELOPE_STATUS_EVENTS` branch, ~line 691, whose docstring
  at ~655 claims "contradictory lifecycle edge fails closed")
- `app/transitions.py` (`ENVELOPE_TRANSITIONS` — the canonical FSM; the single source of legal edges)
- `docs/adr/ADR-010-execution-envelope.md` §3 (the state machine) + `tests/test_wo0125_envelope_replay_parity.py`

## Allowed paths

```yaml
allowed_paths:
  - app/events/projectors.py
  - tests/**
  - docs/INVARIANTS.md          # cross-reference only if a replay-legality invariant is apt
  - work/review/REV-0038/        # request.md staging
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**                # replay reads the log; it never changes what stores WRITE
  - app/transitions.py          # ENVELOPE_TRANSITIONS is the authority, consumed not edited
  - app/monitoring.py
  - docs/adr/**
```

## Required behavior

- [x] GATE: confirm the exact gap — the status-event branch checks payload `from`/`to` against
      current state + event-type, but never consults `ENVELOPE_TRANSITIONS`, so any `(from, to)`
      pair whose endpoints happen to match is accepted even when the FSM forbids the edge.
- [x] Validate each replayed lifecycle edge against `ENVELOPE_TRANSITIONS[from]`: an illegal
      edge raises `ProjectionError` (fail closed), consistent with the function's docstring and
      with how the stores' own FSM refuses to PRODUCE such an event.
- [x] Exhaustive allowed/forbidden transition tests: for every state, every legal edge projects
      and every illegal edge fails closed — including the terminal states (empty outgoing sets)
      and the `FROZEN → COMPLETED` deliberate non-edge (transitions.py comment). Do NOT weaken
      any existing WO-0125 pin.
- [x] Confirm no legitimately-produced event stream is newly rejected (the stores only emit
      legal edges) — run the full existing replay/parity + conformance corpus green.
- [x] Stage `work/review/REV-0038/request.md` for the Claude seat.

## Acceptance criteria

- [x] A synthetic FSM-illegal transition (e.g. `PENDING → COMPLETED`) fails closed with
      `ProjectionError`; every legal transition still projects. Both replay + read-model paths.
- [x] Full replay/parity/conformance corpus green; `ruff`/`mypy`/`pytest` green.
- [x] `status: REVIEW`, REV-0038 staged; Fable DONE with evidence. No disposition/merge until
      the packet returns ACCEPT/ACCEPT-WITH-CHANGES.

## Stop conditions

Stop if enforcing legality would reject a legitimately-produced stream — that would mean the
FSM and the producers disagree, a FINDING to surface, not paper over. Independent of the store
files; may run parallel to WO-0130/0132/0133.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.

## Fable implementation record — staged for independent review

```yaml
fable_gate:
  goal: "Make envelope replay reject every lifecycle edge forbidden by the canonical FSM while preserving every legitimate producer stream."
  assumptions:
    - "ENVELOPE_TRANSITIONS is the accepted single source of legal envelope edges and is not changed by this WO."
    - "The operator authorizes this narrow event-truth interpretation fix only; independent review remains mandatory before reliance."
    - "PENDING is established by ENVELOPE_CREATED and has no representable lifecycle target event."
  approach: "Reproduce the missing graph check, build the full representable edge matrix, consume ENVELOPE_TRANSITIONS in project_envelopes, and mutation-prove direct plus aggregate read-model failure."
  out_of_scope:
    - "FSM edits, event/schema vocabulary, stores, monitoring, facade/API/cockpit, ADR/INV amendments, broker IO, credentials, and live trading."
  done_when:
    - "All 15 legal representable edges project and all 75 illegal representable edges raise ProjectionError."
    - "Direct replay and project_read_models both kill removal of the membership check."
    - "Existing replay/parity/conformance and full repository gates remain green."
    - "REV-0038 is staged and the WO stops at REVIEW."
  blast_radius: "pure envelope event-log replay and derived read-model interpretation"
```

```yaml
fable_fix:
  symptom: "A correctly shaped synthetic PENDING-to-COMPLETED lifecycle event was accepted and projected."
  root_cause: "The projector checked payload from against current state and payload to against the event-type target, but never checked the resulting edge against ENVELOPE_TRANSITIONS."
  evidence: "Untouched probe printed ILLEGAL_EDGE_ACCEPTED=completed; the new pending-to-completed node failed with DID NOT RAISE ProjectionError."
  fix: "After identity/from/to validation and before any status mutation, require the event target in ENVELOPE_TRANSITIONS[current.status], otherwise raise ProjectionError."
  regression_test: "90-pair legal/illegal matrix plus test_read_model_projection_rejects_fsm_illegal_envelope_transition"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The old terminal-fold parametrization treated ACTIVE-to-CANCELLED as a valid producer edge."
  root_cause: "The test grouped every terminal target under an ACTIVE prefix even though canonical cancellation is legal only from PENDING, APPROVED, or FROZEN."
  evidence: "ENVELOPE_TRANSITIONS has no ACTIVE-to-CANCELLED edge; the exhaustive matrix classifies it forbidden."
  fix: "Use FROZEN-to-CANCELLED for the positive terminal fold and retain ACTIVE-to-CANCELLED as an explicit forbidden-matrix node."
  regression_test: "test_terminal_lifecycle_event_folds_status; test_replay_rejects_every_fsm_illegal_envelope_transition[active-to-cancelled]"
  red_green_verified: true
  attempt: 1
```

### Fresh evidence

| Classification | Command | Decisive output |
|---|---|---|
| VERIFIED | untouched WO-0125 replay baseline | `14 passed`. |
| VERIFIED (GATE) | direct synthetic `PENDING → COMPLETED` probe before test/code edits | `ILLEGAL_EDGE_ACCEPTED=completed`. |
| VERIFIED (RED) | exhaustive forbidden node `pending-to-completed` before projector fix | `DID NOT RAISE ProjectionError`. |
| VERIFIED | legal-edge, terminal-fold, and vocabulary controls before fix | `22 passed`. |
| VERIFIED (GREEN) | full WO-0125 replay/parity file after fix | `106 passed`. |
| VERIFIED (mutation RED) | disable graph-membership check; run direct + aggregate illegal nodes | `2 failed`; both paths did not raise. Mutation restored. |
| VERIFIED | existing replay/parity/conformance corpus across eight files | `282` collected nodes; exit `0`; six conformance skips. |
| VERIFIED | `ruff check .` | `All checks passed!` |
| VERIFIED | `mypy app/` | `Success: no issues found in 70 source files`. |
| VERIFIED | `lint-imports` | `Contracts: 6 kept, 0 broken`. |
| VERIFIED | full `pytest -q -p no:cacheprovider --basetemp <unique OS temp>` on `b99d8c0` | exit `0` after `395.6s`; `11 skipped`, `1 xfailed`; fresh collection counted `4205` nodes. |
| VERIFIED | `git diff --check cf50f11..b99d8c0` | exit `0`. |

```yaml
fable_done:
  task: "WO-0131 gated envelope replay FSM legality implementation stage"
  done_when_results:
    - "VERIFIED: 15/15 legal and 75/75 illegal representable FSM edges have explicit expected outcomes."
    - "VERIFIED: direct replay and aggregate read-model paths fail closed and kill a removed check."
    - "VERIFIED: no legitimate replay/parity/conformance producer stream is newly rejected."
    - "VERIFIED: static/import and full 4205-node gates exit green."
    - "UNVERIFIED: independent REV-0038 verdict and disposition remain outstanding; this WO is not closed."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Gate, red, green, mutation, producer-parity, static, and full-corpus evidence above."
  status: VERIFIED
```
