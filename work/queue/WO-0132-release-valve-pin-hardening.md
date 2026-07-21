---
type: Work Order
title: "Release-valve pin hardening: HUMAN_ATTESTED fill-rail direct pin (REV-0035 P1-1) + claim_occurrence conservatism (P2-1)"
status: DRAFT
work_order_id: WO-0132
wave: ultra-batch remediation (post-review)
model_tier: strong
risk: medium
disposition: []
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

- [ ] **P1-1 (the pin):** add a DIRECT unit pin on `plan_append_fill`/`append_fill` with
      `authority=EventAuthority.HUMAN_ATTESTED`, both stores, proving (a) order-level cumulative
      overfill → `FILL_REJECT` (NOT `fill_overfill_quarantined`), and (b) a SELL crossing flat →
      `fill_rejected_negative_position`. The pin must NOT route through the ingest command's
      upstream guards — it exercises the `plan_append_fill` rail directly, so the mutation
      `authority in (BROKER_AUTHORITATIVE, HUMAN_ATTESTED)` at `core.py:586` turns exactly this
      pin RED. Include the mutation-proof evidence.
- [ ] **P2-1 (conservatism):** make the `SUBMIT_RECOVERY_OPERATOR_RECONCILED`-with-no-occurrence
      branch in both `direct_sell_order_may_execute` and `project_envelope_obligation`
      fail-closed (leave intervals open / mark invalid), instead of `claim_open.clear();
      venue_open.clear()`. This is currently unreachable (both stores fail closed before writing
      such an event), so it is defense-in-depth: add an assertion or a conservative default so a
      future emitter cannot silently degrade contribution-only isolation to order-wide clearing.
- [ ] No change to the release/ingest command semantics or the provenance vocabulary — this is
      test-adequacy plus a defensive branch. The existing WO-0114 pins stay green.

## Acceptance criteria

- [ ] The new `HUMAN_ATTESTED` fill-rail pin exists, passes, and turns RED under the
      `core.py:586` mutation (pasted red→green→restored evidence), both stores.
- [ ] The `claim_occurrence`-absent branch is conservative; a targeted test proves it.
- [ ] Full WO-0114 + fills + hardening corpus green; `ruff`/`mypy`/`pytest` green.
- [ ] Fable DONE with evidence. The Claude seat re-verifies the mutation and appends the
      REV-0035 disposition (RESOLVED, remediated_by WO-0132).

## Stop conditions

Stop if closing the pin reveals the shipping behavior is actually wrong (i.e. `HUMAN_ATTESTED`
overfill is NOT rejected today) — that would be a live P0, escalate immediately. Sequenced
after nothing, but shares `app/store/core.py` with WO-0124's already-landed code — rebase, don't
conflict.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
