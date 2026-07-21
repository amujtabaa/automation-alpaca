---
type: Work Order
title: "Envelope replay must fail closed on FSM-illegal lifecycle transitions"
status: DRAFT
work_order_id: WO-0131
wave: ultra-batch remediation (post-review)
model_tier: strong
risk: medium
disposition: []
owner: Ameen / implementer: Codex remediation session
created: 2026-07-21
gated_surface: event-log-truth (replay/read-model interpretation) — human-gated; needs its own review
---

# Work Order: the replay projector's own contract — fail closed on impossible history

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

- [ ] GATE: confirm the exact gap — the status-event branch checks payload `from`/`to` against
      current state + event-type, but never consults `ENVELOPE_TRANSITIONS`, so any `(from, to)`
      pair whose endpoints happen to match is accepted even when the FSM forbids the edge.
- [ ] Validate each replayed lifecycle edge against `ENVELOPE_TRANSITIONS[from]`: an illegal
      edge raises `ProjectionError` (fail closed), consistent with the function's docstring and
      with how the stores' own FSM refuses to PRODUCE such an event.
- [ ] Exhaustive allowed/forbidden transition tests: for every state, every legal edge projects
      and every illegal edge fails closed — including the terminal states (empty outgoing sets)
      and the `FROZEN → COMPLETED` deliberate non-edge (transitions.py comment). Do NOT weaken
      any existing WO-0125 pin.
- [ ] Confirm no legitimately-produced event stream is newly rejected (the stores only emit
      legal edges) — run the full existing replay/parity + conformance corpus green.
- [ ] Stage `work/review/REV-0038/request.md` for the Claude seat.

## Acceptance criteria

- [ ] A synthetic FSM-illegal transition (e.g. `PENDING → COMPLETED`) fails closed with
      `ProjectionError`; every legal transition still projects. Both replay + read-model paths.
- [ ] Full replay/parity/conformance corpus green; `ruff`/`mypy`/`pytest` green.
- [ ] `status: REVIEW`, REV-0038 staged; Fable DONE with evidence. No disposition/merge until
      the packet returns ACCEPT/ACCEPT-WITH-CHANGES.

## Stop conditions

Stop if enforcing legality would reject a legitimately-produced stream — that would mean the
FSM and the producers disagree, a FINDING to surface, not paper over. Independent of the store
files; may run parallel to WO-0130/0132/0133.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.
