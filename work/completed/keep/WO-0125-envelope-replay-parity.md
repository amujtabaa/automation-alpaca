---
type: Work Order
title: "Envelope action/replay parity: projector + dual-store/read-model coverage (CC-04, re-cut from WO-0029)"
status: CLOSED
work_order_id: WO-0125
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: mid
risk: medium
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen / implementer TBD
created: 2026-07-20
gated_surface: none expected (read-model/replay coverage over existing events; no truth change)
---

# Work Order: the envelope event family folds in replay/parity like everything else

## Goal

Close WO-0029's verified-open CC-04: the envelope event family is covered by an
`app/events/` projector, included in the dual-store / read-model parity verification, and
folded by replay tests — so envelope state is reconstructable from the log by the same
machinery that guards every other entity, not only by store-internal code.

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (CC-04)
- `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella)
- `work/review/AUDIT-0002-priorwork/report.md` F005 (verified-open status)
- `app/events/projectors.py` + `app/events/replay.py` (the pattern to extend)
- `tests/test_wo0036_r2_close_and_recovery_ownership.py:299-333` (the WO-0109 Cluster D
  full-model comparator — GATE: how much of CC-04 did post-R2 parity work already cover?)
- `docs/adr/ADR-010-execution-envelope.md` §6 (the full envelope event family to fold)

## Allowed paths

```yaml
allowed_paths:
  - app/events/**
  - tests/**
  - pkl/architecture/testing-model.md
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**             # projection reads the log; it never changes what stores write
  - app/monitoring.py
  - app/models.py
  - docs/adr/**
```

## Required behavior

- [x] GATE first (load-bearing): the R2/WO-0109 era added substantial parity machinery AFTER
      this finding was written. Re-derive exactly what remains uncovered (envelope projector in
      `app/events/`? the envelope surface in `verify_dual_store_parity`? replay folds for all
      envelope event types incl. `ENVELOPE_FILL_ATTRIBUTED`?) and implement ONLY the verified gap.
      If the gap turns out fully closed, the WO ends as a documented no-op with evidence — that
      is a valid outcome.
- [x] Any new projector is pure, deterministic, and consistent with store-derived state on both
      stores (parity-pinned); replay tests fold the complete current event family.
- [x] Red-first for each genuinely-new coverage piece; no store behavior changes.

## Acceptance criteria

- [x] The verified gap list is closed (or evidenced empty); parity/replay pins green both stores.
- [x] Full gates green; Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop if closing the gap would require changing what any store writes (event truth) — that is a
gated change belonging elsewhere. Independent of Lane P (no shared files); may run any time.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.

## Fable gate

```yaml
fable_gate:
  goal: "Close only the verified residual CC-04 gap by projecting the current envelope event family and adding envelope state to replay/read-model parity."
  verified_residual_gap:
    - "The post-R2 full-stream comparator proves raw audit/execution stream equality, but app/events/projectors.py still has no envelope projector."
    - "ReadModelProjection and verify_dual_store_readmodel_parity omit envelopes, so equivalent event logs can pass while reconstructed envelope status or remaining quantity diverges."
    - "No app/events replay test folds the complete current envelope vocabulary, including envelope-correlated FILL and ENVELOPE_FILL_ATTRIBUTED repair markers."
  already_covered:
    - "Store write-path parity and complete raw event payload comparison are already pinned by WO-0109/R2 and will not be duplicated or changed."
    - "Envelope write semantics and event truth are out of scope; this work reads existing events only."
  approach: "Write red tests for complete-family replay, store-state reconstruction on both stores, dual-store parity, and comparator divergence; then add a pure fail-closed envelope projector and wire it into the existing read-model verifier."
  out_of_scope:
    - "any app/store/** behavior or event emission change"
    - "app/models.py or ADR changes"
    - "replace-budget policy/projection owned by WO-0126"
    - "disposition-cancel eventing owned by WO-0124"
  done_when:
    - "Every current envelope event kind is explicitly classified and replay-covered, including no-op metadata/action events and fill-attribution debits."
    - "Projected envelope status and remaining quantity equal each store's read model after a non-trivial lifecycle."
    - "Dual-store envelope parity is failure-capable and all full gates pass."
    - "Close-out status, disposition, ledger, move, scoreboard, and evidence ship atomically."
  blast_radius: "app/events/**, tests/**, testing-model PKL, and work records"
```

## Fable fixes

```yaml
fable_fixes:
  - symptom: "The new WO-0125 test module failed during collection."
    root_cause: "The verified residual gap was real: app.events.projectors exported no envelope event vocabulary or projector API."
    evidence: "The red-first run exited 2 with ImportError for ENVELOPE_EVENT_TYPES before implementation."
    fix: "Add an explicit vocabulary ratchet, pure EnvelopeProjection fold, and read-model parity wiring."
    regression_test: "tests/test_wo0125_envelope_replay_parity.py"
    red_green_verified: true
    attempt: 1
  - symptom: "The first implementation run raised NameError while validating envelope side identity."
    root_cause: "The projector referenced OrderSide.SELL but the model enum was omitted from its import list."
    evidence: "Eleven focused tests failed at _created_envelope_projection with NameError: OrderSide is not defined."
    fix: "Import OrderSide from app.models; retain the fail-closed SELL identity check."
    regression_test: "tests/test_wo0125_envelope_replay_parity.py::test_replay_folds_actions_fills_attribution_freeze_and_resume"
    red_green_verified: true
    attempt: 2
  - symptom: "The first real-store replay fixture staged no child and froze the envelope for plan divergence."
    root_cause: "The fixed test clock resolved to PRE_MARKET while the fixture mandate allowed only REGULAR, so the store correctly rejected the action before the intended replay path."
    evidence: "Both stores returned outcome=divergence with rail detail phase pre_market not in allowed ['regular']."
    fix: "Permit all existing session phases in the test-only mandate so the fixture exercises replay rather than a phase-rail rejection."
    regression_test: "tests/test_wo0125_envelope_replay_parity.py::test_projection_matches_each_store_read_model"
    red_green_verified: true
    attempt: 2
```

## Fresh evidence

```yaml
evidence:
  - command: "red-first focused pytest with unique OS-temp basetemp"
    result: PASS
    decisive_output: "Collection exited 2: ImportError for missing ENVELOPE_EVENT_TYPES before implementation."
  - command: "temporary parity-wiring and envelope-debit mutations"
    result: PASS
    decisive_output: "Removing envelopes from project_read_models failed both store cases; dropping a debit failed the next attribution-chain check. Both mutations were reverted with apply_patch."
  - command: "focused WO-0125 tests"
    result: PASS
    decisive_output: "14 passed in 0.54s, including both stores and an intentionally divergent dual-store log."
  - command: "WO-0125 plus Phase 6B, WO-0016 envelope-event, and WO-0036 R2 regressions"
    result: PASS
    decisive_output: "49 passed in 4.05s."
  - command: "ruff check changed Python; mypy app/; lint-imports"
    result: PASS
    decisive_output: "Ruff passed; mypy succeeded on 64 source files; all 6 import contracts kept."
  - command: "full pytest with addopts cleared, cache provider disabled, and unique OS-temp basetemp"
    result: PASS
    decisive_output: "3881 passed, 11 skipped, 1 xfailed in 473.93s."
  - command: "five AI-OS checks; Fable; complete work-order scope; context hygiene"
    result: PASS
    decisive_output: "Install, version, ledger, PKL, disposition, Fable, and scope passed; hygiene reported 0 violations and one advisory for review-gated WO-0127 exceeding its line budget."
```

The 11 skips are the existing three credential-gated paper-integration cases, six disclosed
Claude-oracle cases, and two shadow-fill internals; the single xfail is the existing structural
hold. No credentials were used. Repository-wide `ruff format --check .` still identifies the
pre-existing out-of-scope reviewer audit probe; all WO-0125 Python files are ruff-formatted.

## Fable done

```yaml
fable_done:
  task: "WO-0125 envelope action/replay parity"
  done_when_results:
    - item: "The residual CC-04 gap was re-derived after R2 and limited to app/events projector/read-model coverage."
      status: MET
    - item: "Every current envelope_* event type is explicitly classified; canonical FILL and ENVELOPE_FILL_ATTRIBUTED both fold the persisted remaining-quantity chain."
      status: MET
    - item: "Projection reconstructs immutable bounds, lifecycle, remaining quantity, and supersession, and matches both store read models."
      status: MET
    - item: "Dual-store comparison is failure-capable and full static/test/AI-OS gates are green."
      status: MET
    - item: "No store, model, monitoring, ADR, or event-emission behavior changed."
      status: MET
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    event_truth_changed: false
  evidence:
    - "14 focused tests passed; 49 adjacent replay/R2 regressions passed"
    - "Two deliberate mutations turned the new pins red"
    - "3881 passed, 11 skipped, 1 expected xfailed in the full suite"
    - "Ruff, mypy, import contracts, five AI-OS checks, and scope passed; hygiene had 0 violations and one WO-0127 size advisory"
  status: VERIFIED
```
