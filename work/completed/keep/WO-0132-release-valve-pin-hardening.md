---
type: Work Order
title: "Release-valve pin hardening: HUMAN_ATTESTED fill-rail direct pin (REV-0035 P1-1) + claim_occurrence conservatism (P2-1)"
status: CLOSED
work_order_id: WO-0132
wave: ultra-batch remediation (post-review)
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen / implementer: Codex remediation session
created: 2026-07-21
gated_surface: release-valve provenance rail (test-adequacy + a defensive core.py branch) — re-verified by the Claude seat
---

# Work Order: close the REV-0035 inert-pin on the release valve's provenance rail

> Remediates the WO-0114 review (REV-0035, ACCEPT-WITH-CHANGES). The shipping behavior is
> CORRECT; the guarding test is missing (an inert pin of the REV-0029 P0-4 class). On
> completion, the Claude seat re-verifies the pin closes the mutation and records it in the
> REV-0035 disposition — no fresh packet needed for a test-adequacy fix, but the mutation
> re-check is mandatory.

## Goal

Make the `HUMAN_ATTESTED` non-broker fill rail directly, failure-capably pinned (so a mutation
treating human evidence as broker-authoritative turns a test RED), and make the release-event
consumers' `claim_occurrence`-absent branch conservative (fail-closed, not over-clearing).

## Context packet

- `work/review/REV-0035/result.md` (P1-1 + P2-1 — the authoritative findings, with the exact
  mutation and file:lines)
- `docs/adr/ADR-012-*` §4 + `work/queue/PD1-R2-PLANNING-PACKAGE.md` §2 D-PD1-1(ii)
  (the "enumerated AND pinned" claim this WO makes true)
- `app/store/core.py:586` (`broker_authoritative = authority is BROKER_AUTHORITATIVE`), the
  overfill (`:588-590`) and negative-position (`:621`) branches
- `app/store/core.py:1332-1339` (`direct_sell_order_may_execute`) + `:1957-1965`
  (`project_envelope_obligation`) — the `claim_occurrence`-None over-clear (P2-1)
- `tests/test_wo0114_pd1_release_valve.py`, `tests/test_review_hardening_gates.py`

## Allowed paths

```yaml
allowed_paths:
  - app/store/core.py            # P2-1 None-branch conservatism ONLY (no rail-semantics change)
  - tests/**
  - docs/adr/ADR-012-*.md        # optional: name the new pin in §4
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/models.py                # no vocabulary change
  - app/facade/**
  - app/api/**
  - cockpit/**
  - app/reconciliation.py
```

## Required behavior

- [x] **P1-1 (the pin):** add a DIRECT unit pin on `plan_append_fill`/`append_fill` with
      `authority=EventAuthority.HUMAN_ATTESTED`, both stores, proving (a) order-level cumulative
      overfill → `FILL_REJECT` (NOT `fill_overfill_quarantined`), and (b) a SELL crossing flat →
      `fill_rejected_negative_position`. The pin must NOT route through the ingest command's
      upstream guards — it exercises the `plan_append_fill` rail directly, so the mutation
      `authority in (BROKER_AUTHORITATIVE, HUMAN_ATTESTED)` at `core.py:586` turns exactly this
      pin RED. Include the mutation-proof evidence.
- [x] **P2-1 (conservatism):** make the `SUBMIT_RECOVERY_OPERATOR_RECONCILED`-with-no-occurrence
      branch in both `direct_sell_order_may_execute` and `project_envelope_obligation`
      fail-closed (leave intervals open / mark invalid), instead of `claim_open.clear();
      venue_open.clear()`. This is currently unreachable (both stores fail closed before writing
      such an event), so it is defense-in-depth: add an assertion or a conservative default so a
      future emitter cannot silently degrade contribution-only isolation to order-wide clearing.
- [x] No change to the release/ingest command semantics or the provenance vocabulary — this is
      test-adequacy plus a defensive branch. The existing WO-0114 pins stay green.

## Acceptance criteria

- [x] The new `HUMAN_ATTESTED` fill-rail pin exists, passes, and turns RED under the
      `core.py:586` mutation (pasted red→green→restored evidence), both stores.
- [x] The `claim_occurrence`-absent branch is conservative; a targeted test proves it.
- [x] Full WO-0114 + fills + hardening corpus green; `ruff`/`mypy`/`pytest` green.
- [x] Fable DONE with evidence. The Claude seat re-verifies the mutation and appends the
      REV-0035 disposition (RESOLVED, remediated_by WO-0132).

## Stop conditions

Stop if closing the pin reveals the shipping behavior is actually wrong (i.e. `HUMAN_ATTESTED`
overfill is NOT rejected today) — that would be a live P0, escalate immediately. Sequenced
after nothing, but shares `app/store/core.py` with WO-0124's already-landed code — rebase, don't
conflict.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.

## Fable verification and close-out

```yaml
fable_gate:
  goal: "Make HUMAN_ATTESTED's strict fill rails failure-capable and make occurrence-less release facts fail closed without changing release or fill semantics."
  assumptions:
    - "D-PD1-1 through D-PD1-4 and ADR-012 Proposed define the complete authorized provenance behavior."
    - "The shipping HUMAN_ATTESTED planner behavior is correct; REV-0035 found test inadequacy, not a live economic-truth defect."
    - "Legitimate release writers always bind claim_occurrence today; the None branches are defense-in-depth for future or corrupt facts."
  approach: "Call plan_append_fill directly under both store fixtures, mutation-prove both rejection rails, then replace order-wide clearing on an unbound release with explicit fail-closed projection outcomes."
  out_of_scope:
    - "Provenance vocabulary, release/fill commands, facade/API/cockpit, schema/DDL, broker calls, ADR acceptance, and REV-0035 disposition."
  done_when:
    - "The reviewer mutation makes memory/SQLite BUY-overfill and SELL-cross nodes red, then all four restore green."
    - "Both projection consumers retain/mark unsafe when a release fact resolves no occurrence."
    - "Focused safety, conformance, static, import, and full repository gates pass."
  blast_radius: "two defensive lifecycle projection branches plus direct tests of the existing human-attested fill rail"
```

```yaml
fable_fix:
  symptom: "REV-0035's HUMAN_ATTESTED-as-broker mutation survived the prior release-valve and hardening corpus."
  root_cause: "Existing operator-fill tests stopped in ingest-level cumulative/position prechecks and never invoked plan_append_fill under a violating HUMAN_ATTESTED input."
  evidence: "The new direct nodes passed on shipping behavior, then all four failed with append != reject under the exact core.py authority mutation."
  fix: "Add a direct plan_append_fill pin for cumulative BUY overfill and SELL crossing flat, parameterized through memory and SQLite fixtures, asserting reject audit shape and absence of fill/quarantine facts."
  regression_test: "test_PIN_human_attested_plan_append_fill_keeps_strict_rails (four nodes)"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "An occurrence-less operator-reconciled fact cleared every open claim and venue interval in two lifecycle projections."
  root_cause: "The unresolved-None fallback treated inability to identify the one authorized occurrence as order-wide terminal authority, contrary to ADR-012's contribution-only release."
  evidence: "Before the fix, direct SELL projected not-live and the terminal envelope child projected valid/released in both store fixtures (four failures)."
  fix: "Return possibly-live for the direct SELL projection; mark the envelope child invalid and retain its obligation. Neither branch clears any interval without an occurrence."
  regression_test: "test_occurrence_less_release_cannot_clear_direct_sell_venue_interval; test_occurrence_less_release_marks_envelope_child_invalid"
  red_green_verified: true
  attempt: 1
```

### Fresh evidence

| Classification | Command | Decisive output |
|---|---|---|
| VERIFIED (RED/GATE) | new direct-pin plus occurrence-less nodes on shipping source | `4 passed, 4 failed`; only the two P2 consumers failed on memory + SQLite. |
| VERIFIED (mutation RED) | exact REV-0035 mutation: treat `HUMAN_ATTESTED` as broker-authoritative; run direct pin | `4 failed`; every node returned `append` instead of `reject`. |
| VERIFIED (restored) | restore authority line; run direct pin | `4 passed`. |
| VERIFIED (GREEN) | all eight WO-0132 nodes after the P2 fix | `8 passed`. |
| VERIFIED | full WO-0114 + cockpit + fills + hardening corpus | 133 collected nodes; exit `0`; only two pre-existing Starlette deprecation warnings. |
| VERIFIED | `ruff check .` | `All checks passed!` |
| VERIFIED | `mypy app/` | `Success: no issues found in 70 source files`. |
| VERIFIED | `lint-imports` | `Contracts: 6 kept, 0 broken`. |
| VERIFIED | both R2 conformance oracles | `83 passed, 6 skipped`; exit `0`. |
| VERIFIED | full `pytest -q -p no:cacheprovider --basetemp <unique OS temp>` | exit `0` after `306.2s`; `11 skipped`, `1 xfailed`; fresh collection counted `4113` nodes. |

```yaml
fable_done:
  task: "WO-0132 release-valve pin hardening"
  done_when_results:
    - "VERIFIED: the exact reviewer mutation is killed by four direct HUMAN_ATTESTED planner nodes across memory and SQLite."
    - "VERIFIED: an occurrence-less release cannot clear direct-SELL or envelope venue exposure."
    - "VERIFIED: release/ingest semantics, vocabulary, schema, API, cockpit, and broker boundaries are unchanged."
    - "VERIFIED: focused, conformance, static/import, and full 4113-node gates exited green."
    - "UNVERIFIED: the independent Claude-seat re-check and REV-0035 disposition remain out-of-session by contract."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Red, exact mutation, restored, focused, conformance, and full-corpus evidence above."
  status: VERIFIED
```
