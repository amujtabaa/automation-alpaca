---
type: Work Order
title: "Signal-endpoint threat model (R5-prep): adversarial requirements checklist for the first external input surface"
status: CLOSED
work_order_id: WO-0136
wave: signal-seat R5 preparation (parallel to R4; doc-only)
model_tier: mid (CLOUD-capable — bounded documentation work per repo-primer execution preference)
risk: low (no code, no gated surface touched; output is advisory input to R5)
owner: Ameen / implementer: any seat (cloud session suitable)
created: 2026-07-22
disposition: [RESULT_SUMMARY_KEPT]
closed: 2026-07-22
gated_surface: none — new analysis doc only. NOT an ADR/spec change; closes out fully in-session. Its findings feed R5's build + R5's review packet; they do not amend accepted text.
---

# Work Order: threat-model the signal ingestion surface before R5 builds it

> **CLOSED (2026-07-22):** Delivered `docs/THREAT_MODEL_SIGNAL_SEAT.md`, an advisory STRIDE threat model with assets/trust boundaries, attacker profiles, per-surface STRIDE rows, ADR-009 A-1/A-4 traceability, pre-found-attack traceability, a numbered GAP register, non-goals, and a zero-orphan self-audit. Disposition `[RESULT_SUMMARY_KEPT]`.

> **Advisory input, not spec.** The deliverable is a NEW analysis document. It proposes; it
> never amends. Any finding that seems to contradict the ACCEPTED ADR-009/spec text is
> recorded as a decision gap for the operator (CLAUDE.md conflict rule) — this WO does not
> edit `docs/adr/**` or `docs/spec/**` under any circumstance.

> **Why now:** the signal seat is the system's FIRST external input surface — everything
> before it was operator-initiated through the cockpit. R5 implements the endpoint, auth,
> and launcher (human-gated). A threat model completed before R5 starts gives the
> implementer an adversarial requirements checklist and gives R5's independent review
> packet a ready-made oracle ("show the control for each row"). Runs in parallel with the
> R4 Codex session — zero file overlap.

## Goal

Produce `docs/THREAT_MODEL_SIGNAL_SEAT.md`: a STRIDE-organized threat model of the signal
ingestion surface (endpoint, producer/operator auth, transport/bind, rails, key custody,
audit trail, conversion hand-off) in which **every threat row terminates in exactly one
of:** an existing accepted control (cited to spec/ADR anchor), an explicitly accepted risk
(with the ratifying decision named), or a GAP that becomes a numbered R5/R6/R7 requirement
or a NEEDS-INPUT operator decision. No orphan threats, no hand-waving.

## Context packet (read fully; the analysis is a synthesis of these, not new invention)

- `docs/adr/ADR-009-signal-seat-boundary.md` (**Accepted 2026-07-21**) — esp. A-1 (transport
  policy, key rotation/revocation, fail-closed mounted-route auth matrix incl. reads,
  credential-presence startup guard, backend-owned launcher + construction-time one-shot
  capability) and A-4 (authenticate → rails → 64 KiB capped read → parse; non-refilling
  invalid budget; one PRODUCER_QUARANTINED per epoch).
- `docs/spec/signal-seat/00..06` — esp. `03-rails.md` (dual-rail design) and
  `04-auth-and-api.md` (route auth matrix).
- `docs/adr/ADR-013-external-ingress.md` (**Proposed** seed) — the Option-C receiver
  architecture; the threat model's internet-attacker section sizes what that ADR must
  eventually answer, WITHOUT approving it.
- Standing ratifications: D-SIG-1 = Option A (localhost producer), D-SIG-3 (`loopback`
  default + `tailnet_serve`; **Funnel forbidden** as a spec-level negative test), D-SIG-4
  (construction-time bind guard), D-SIG-5 (flag-on gates ALL sensitive reads), D-SIG-6
  (env-injected static keys, overlap rotation), D-HOST-1 (localhost is a load-bearing
  security boundary; VPS gated on an auth ADR).
- **The pre-found attack corpus (mandatory rows; cite as archive-ref provenance, plan §2 —
  never bare REV ids):**
  - REV-0022 F-001 (master packet): unauthenticated reads / transport-credential boundary.
  - archive REV-0024 @ `origin/archive/claude-wo-0001-install-checks-2x5ys8`: the
    ASGI-seam bind-guard unenforceability; the **paced-hostility hole** (10,080 events over
    7 days at 1 req/min without breaching a refill bucket — the attack that produced the
    non-refilling budget).
  - archive REV-0025 @ same ref: reachable-503 listener; non-mutation-sensitive launch
    proof; non-linearizable/non-durable budget; joint-enablement contradiction;
    **`POST /api/session/close` missing from the auth matrix**.
- `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §4 (the auth options analysis) and §10
  (ratification record).

## Required content (the document's skeleton — done-when includes every item)

- [ ] **Assets & trust boundaries.** Producer keys, operator key, event-log integrity
      (append-only audit truth), the approval→conversion integrity chain (a signal NEVER
      executes without HUMAN approval — the crown jewel), host/port exposure, cockpit
      availability. Boundaries: producer process ↔ FastAPI (localhost, Option A);
      tailnet node ↔ serve (Option B config flip); internet ↔ receiver (Option C, FUTURE,
      forbidden today); browser ↔ cockpit ↔ API; env custody of static keys.
- [ ] **Attacker profiles.** Malicious/compromised local producer process; a non-producer
      local process on the same host; a tailnet node (Option B posture); an internet
      attacker (must be shown STRUCTURALLY excluded today: loopback bind + bind guard +
      Funnel prohibition); a compromised operator browser context; and operator misuse
      (fat-finger approval of a stale/spoofed thesis — misuse case, not attacker, but the
      approval payload rules exist for it).
- [ ] **STRIDE table per surface** — `POST /api/signals`, operator read/approve/reject
      routes, producer-release route, launcher/bind path, key custody/rotation, event
      log/audit, cockpit header plumbing. Spoofing (producer identity binding — wire
      `producer_id` deliberately absent, credential-derived); Tampering (payload_hash
      conflict detection; suggested-values-are-advisory); Repudiation (event-per-fact,
      terminal-at-ingest recording); Information disclosure (error verbosity, docs routes
      gated, thesis/provenance stored-and-displayed-verbatim → cockpit rendering note);
      DoS (boundary-rejection before body read, 64 KiB cap, dual rails, budget
      linearizability); Elevation (signal → conversion requires HUMAN approval + A-2
      atomicity + exposure predicate — cite INV-090 path).
- [ ] **Traceability appendix A:** every ADR-009 A-1 and A-4 clause ↔ at least one threat
      row it mitigates. A clause mitigating nothing, or a threat with no clause, is itself
      a finding.
- [ ] **Traceability appendix B:** every pre-found attack (context packet list) has a row
      showing which ACCEPTED control now covers it — or a GAP.
- [ ] **GAP register:** each gap numbered, assigned an owner rung (R5 / R6 / R7 / ADR-013 /
      operator NEEDS-INPUT), phrased as a testable requirement ("R5 must refuse …", never
      "R5 should consider …").
- [ ] **Non-goals stated in the doc:** no code, no spec/ADR edits, no penetration testing,
      no new dependencies; Option C analysis sizes ADR-013 but approves nothing.

## Allowed paths

```yaml
allowed_paths:
  - docs/THREAT_MODEL_SIGNAL_SEAT.md   # the deliverable (NEW file)
  - work/**                            # activation, close-out, ledger line
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - cockpit/**
  - tests/**
  - docs/adr/**        # findings feed decisions; they never edit accepted text
  - docs/spec/**
  - pkl/**             # PKL distillation happens at close-out only if warranted, via disposition
```

## Acceptance criteria

- [ ] Every threat row terminates in control-with-anchor / accepted-risk-with-decision /
      numbered GAP. Zero orphans (self-audit table at the end of the doc).
- [ ] Both traceability appendices complete (A-1/A-4 clauses; pre-found attacks).
- [ ] All archive citations use archive-ref provenance form.
- [ ] `python .ai-os/scripts/check_work_order_disposition.py` passes; docs-only diff
      (verify with `git diff --stat`).
- [ ] Close-out ships with the work (non-gated WO): status flip + disposition + ledger line
      + file move to `work/completed/keep/` in the finishing commit.

## Stop conditions

- Analysis surfaces what looks like a **P0-equivalent hole in ACCEPTED text** (a threat the
  accepted controls demonstrably fail to cover on a safety surface) → STOP, record the
  decision gap, escalate to the operator immediately. Do not quietly downgrade it to a GAP
  row, and do not draft an ADR amendment yourself.
- Scope pressure toward code/tests/spec edits → refuse; those belong to R5/R6/R7.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (add `PKL_UPDATED` only if a distilled security-posture
PKL page is genuinely warranted at close-out). The GAP register's R5 rows get copied into
the R5 WO draft by the planning seat when R5 is chartered — that hand-off is the planning
seat's job, not this WO's.
