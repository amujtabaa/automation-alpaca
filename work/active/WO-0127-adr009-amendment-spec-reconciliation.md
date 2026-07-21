---
type: Work Order
title: "Signal Seat R1: ADR-009 remediation amendment + spec reconciliation + REV-0034 staging"
status: REVIEW
work_order_id: WO-0127
wave: signal-seat revival (O-3 path a; ladder step R1)
model_tier: strong
risk: high
disposition: []
owner: Ameen (approves amendment text) / implementer: Codex ultra session
created: 2026-07-20
gated_surface: ADR change (human-gated); ADR-009 status stays Proposed until REV-0034 ACCEPT
---

# Work Order: land the remediated ADR-009 + spec suite on master, stage the re-review

> Docs/specs/queue ONLY — zero app/test code. Executes the reconciliation plan §3/§6 step R1
> (`work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md`). Governed by the ratified decisions in the
> plan §10 and the kickoff decision block (D-SIG-1..8). **ADR-009 status remains `Proposed`**
> — the flip to Accepted happens only after REV-0034 returns ACCEPT/ACCEPT-WITH-CHANGES and
> Ameen ratifies. Archive refs are provenance only; archive REV-0024..0027 ids never port.

## Goal

Master's ADR-009 + signal-seat spec suite carry the archive's three-review-rounds-hardened
remediation text (A-1..A-4), corrected for today's tree — so one fresh independent review
(REV-0034) can clear the REV-0022 gate properly.

## Context packet

- `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §3 (finding-by-finding actions), §4 (auth),
  §9 (exposure-predicate design), §10 (ratifications) — THE source of truth for this WO
- `docs/adr/ADR-009-signal-seat-boundary.md` (master, Proposed) + archive versions via
  `git show 'origin/archive/claude-wo-0001-install-checks-2x5ys8:<path>'`
- `work/review/REV-0022/` (the open BLOCK this remediates)
- `docs/adr/ADR-010-execution-envelope.md` + `docs/INVARIANTS.md` INV-087/090/091 (the
  invariants the A-3 rewrite must consume, per plan §9)
- `work/queue/PD1-R2-PLANNING-PACKAGE.md` D-HOST-1/D-013b records (transport posture)

## Allowed paths

```yaml
allowed_paths:
  - docs/adr/ADR-009-signal-seat-boundary.md
  - docs/adr/ADR-013-external-ingress.md     # D-SIG-9 Proposed-only seed
  - docs/spec/signal-seat/**
  - pkl/architecture/signal-seat.md
  - docs/INVARIANTS.md            # cross-references ONLY (no invariant semantics change)
  - work/queue/WO-0102-signal-ingestion-endpoint.md   # re-scope per plan §5/§8-11
  - work/queue/WO-0103-signal-approval-surface.md
  - work/queue/WO-0104-signal-rails.md
  - work/review/DISPATCH.md       # ported with fixes per plan §5
  - work/review/REV-0034/         # request.md staging ONLY
  - work/**                       # close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - cockpit/**
  - .github/**
```

## Required behavior

- [x] Port amendments A-1..A-4 onto master's ADR-009 per plan §3's per-finding "Master action"
      column, including: `tls_proxy` → `tailnet_serve` narrowing + Funnel-prohibition as a
      spec-level negative-test clause (D-SIG-3); the D-SIG-1 Option A producer topology as the
      v1 posture with Option B as a config flip; route matrix extended to the post-fork
      envelope routes + `POST /api/session/close`; all anchors refreshed to current file:line;
      every archive REV citation converted to archive-ref provenance.
- [x] **A-3 exposure rewrite:** replace the archive's hand-rolled committed-sell-exposure text
      with the plan §9 design verbatim in intent (shared pure `project_committed_sell_exposure`
      consuming the obligation projection / `RECOVERY_OPEN_STATUSES` / INV-091 coalescing;
      fail-closed on ambiguity; breakdown-carrying refusals; cross-consistency property pin).
- [x] **Multi-exit clause:** per D-SIG-7's ratified answer — if DECLINED (recommended), the
      archive's multi-exit/single-flight relaxation is stricken and ADR-009 states signal
      conversion conforms to INV-087 single-mandate + existing single-flight; if accepted, the
      clause is rewritten against INV-087/090 and flagged prominently for REV-0034.
- [x] **Conversion semantics:** per D-SIG-8's ratified answer — v1 signal conversion mints the
      SAME Candidate/SellIntent objects the cockpit does; downstream execution is byte-identical
      to manual flow (envelope where the operator delegates); no new execution lane.
- [x] **External-ingress seed:** per D-SIG-9, create Proposed-only ADR-013 for the thin public
      HMAC/secret-authenticating Receiver that forwards privately as a keyed producer; the
      trading API is never public; D-HOST-1 deployment/auth ADR acceptance + review are prerequisites.
- [x] Spec files 00-04 ported with plan §5 mechanical fixes; 05-conversion sell-half and
      06-invariants REWRITTEN per plan §5; pkl page stays draft/medium authority.
- [x] WO-0102/0103/0104 re-scoped per plan §5 + §8-11 (status stays gated/draft; launcher trio
      + main.py scope widened in WO-0102's allowed paths).
- [x] Stage `work/review/REV-0034/request.md`: one fresh packet against the FINAL text,
      explicitly flagging every never-reviewed item (A-1 clause 6 / D-1a; final A-4; the two
      locked A-3 clauses; the D-SIG-7 outcome). Reviewer: the Claude seat (cross-model rule —
      the review itself runs OUT of this session).
- [x] The amendment text is human-gated: this WO ends its session at `status: REVIEW` with
      REV-0034 staged; Ameen's text approval happens at the post-session merge review together
      with the REV-0034 disposition. Never stall mid-session waiting for it.

## Acceptance criteria

- [x] Every plan §3 "Master action" executed; zero app/test files touched (`git diff --stat`).
- [x] ADR-009 still `Proposed` with a dated "remediation drafted, REV-0034 pending" banner.
- [x] REV-0034 request staged and self-contained against semantic head `7fa9985`; per the batch's
      explicit review-gated exception, this WO stays in `work/active/` and receives no ledger row
      or completion disposition until independent review and human text approval.
- [x] Fable DONE with evidence (anchor-verification greps pasted for every refreshed citation).

## Stop conditions

Stop and batch NEEDS-INPUT if any archive clause cannot be honestly rewritten under a ratified
decision (never improvise a third semantic); if INVARIANTS.md would need a semantic (not
cross-reference) edit, that is out of scope. Rollback: revert; docs-only.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (ADR amendment recorded in-place; ADR_CREATED not applicable).

Not applied at this gate. REV-0034 and Ameen's text approval remain outstanding, so disposition,
ledger append, and move to `work/completed/` are deliberately deferred.

## Evidence and Fable handoff

### Red-first contract probe

The pre-build probe failed on the absent/old contract exactly as intended:

```text
RED: ADR-013 missing
RED: REV-0034 request missing
RED: ADR-009 lacks tailnet_serve
RED: ADR-009 lacks shared exposure projection
RED: 03-rails still specifies withdrawn interim ceiling
```

### Fresh verification evidence

```text
PowerShell semantic-contract probe
PASS: all seven 00-06 specs exist
PASS: ADR-009 remains Proposed and REV-0034-pending
PASS: ADR-009 contains A-1 through A-4
PASS: tailnet_serve vocabulary
PASS: Funnel forbidden
PASS: backend-owned launcher
PASS: flag-on sensitive reads gated
PASS: multi-key overlap rotation
PASS: shared exposure projection
PASS: recovery-open-status source
PASS: accepted-submit truth source
PASS: D-SIG-7 preserves single-flight and INV-087
PASS: D-SIG-8 ordinary objects
PASS: ADR-013 remains Proposed
PASS: ADR-013 receiver authentication
PASS: ADR-013 trading API never public
PASS: ADR-013 D-HOST-1 prerequisite
PASS: WO-0102 remains draft
PASS: WO-0103 remains draft
PASS: WO-0104 remains draft
PASS: WO-0102 launcher trio scope
PASS: WO-0103 shared exposure
PASS: WO-0103 ordinary objects
PASS: WO-0104 bounded audit epoch
PASS: PKL stays draft
PASS: PKL stays medium authority
PASS: REV-0034 flags never-reviewed clauses
CONTRACT CHECK PASSED
```

```text
git diff --name-only 87aa950 | python .ai-os/scripts/check_work_order_scope.py work/active/WO-0127-adr009-amendment-spec-reconciliation.md
SCOPE CHECK PASSED

python .ai-os/scripts/check_pkl.py pkl/architecture
PKL CHECK PASSED
python .ai-os/scripts/check_work_order_disposition.py
DISPOSITION CHECK PASSED
python .ai-os/scripts/check_ledger.py
LEDGER CHECK PASSED
python .ai-os/scripts/check_install.py
INSTALL CHECK PASSED
python .ai-os/scripts/check_fable_done.py work/active/WO-0127-adr009-amendment-spec-reconciliation.md
FABLE CHECK PASSED
python -m pytest .ai-os/scripts/tests/test_phase3_checks.py -q --basetemp "$env:TEMP\codex-wo0127-phase3"
.................                                                        [100%]
```

Current-tree anchor verification for every source anchor carried by the refreshed ADR/spec:

```text
app/store/core.py
981:    qty = candidate.suggested_quantity
992:    limit_price = candidate.suggested_limit_price
887:def plan_create_order_for_candidate(
1401:def project_envelope_obligation(

app/facade/store_backed.py
786:            await gate.approve(candidate_id)
787:            await self._store.create_order_for_candidate(

app/models.py
893:RECOVERY_OPEN_STATUSES = frozenset({RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW})

app/api/routes_system.py
48:@router.post("/session/close", response_model=SessionRecord)

app/api/routes_trading.py
289:@router.get("/envelopes", response_model=list[ExecutionEnvelope])
299:@router.post("/envelopes/approve", response_model=ExecutionEnvelope)
318:@router.post("/envelopes/{envelope_id}/cancel", response_model=ExecutionEnvelope)

docs/INVARIANTS.md
829:**INV-087 — At most one ACTIVE execution envelope per SYMBOL.**
891:**INV-090 — A SellIntent's envelope-owner lifecycle is decided ONLY by the
978:**INV-091 — Durable submit progress cannot disappear or be blindly repeated.**
```

```text
Changed-path negative control: zero app/, tests/, cockpit/, or .github/ paths.
git diff --check 87aa950: PASS
Artifact-residue negative control: no truncation marker, mojibake, duplicate archive qualifier,
or future 2026-07-21 date: PASS
Premature-acceptance negative control: ADRs remain Proposed; specs/PKL/WOs remain REVIEW/draft: PASS
docs/INVARIANTS.md diff: one additive non-normative cross-reference; zero invariant-body edits.
```

```yaml
fable_gate:
  task: "WO-0127 ADR-009 remediation, Signal Seat spec reconciliation, and REV-0034 staging"
  mode: FULL
  assumptions:
    - "The kickoff decision block is the only ratification source; D-SIG-1..9 are binding."
    - "Archive packets are provenance only and cannot clear master's REV-0022 gate."
    - "This is docs/spec/queue work only; no runtime or schema implementation is authorized."
  out_of_scope:
    - "Independent REV-0034 review or self-certification"
    - "ADR acceptance, fresh signal_records DDL approval, or WO-0102..0104 implementation"
    - "Any application, test, cockpit, CI, live-trading, or credential change"
  done_when: "A-1..A-4 and D-SIG-1..9 are reconciled to current truth, downstream drafts remain gated, REV-0034 is staged, and fresh scope/governance/anchor evidence passes."
  red_evidence: "The five-clause pre-build probe failed on missing ADR-013/REV-0034, old transport/exposure text, and the withdrawn interim ceiling."
```

```yaml
fable_fix:
  symptom: "The current-anchor sweep found ADR-009 still cited app/store/core.py:641+ for Candidate quantity/price, and draft metadata used a future 2026-07-21 date."
  root_cause: "One archive-derived sizing paragraph and generated metadata escaped the first current-tree/date normalization pass."
  evidence: "Current source places the sizing reads at app/store/core.py:981 and :992; the session kickoff and environment date are 2026-07-20."
  fix: "Changed the sizing citation to :981-998, the split-await citation to :786-789, propagated both to the spec/review packet, and normalized all draft dates to 2026-07-20."
  regression_test: "The refreshed anchor greps, semantic contract, residue negative control, and git diff checks all pass."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_done:
  task: "WO-0127 ADR-009 remediation, Signal Seat spec reconciliation, and REV-0034 staging"
  done_when_results:
    - item: "Plan section 3 A-1 through A-4 remediations and ratified D-SIG outcomes are carried by ADR-009/specs"
      status: MET
      evidence: "Semantic contract probe passed all clauses; ADR-009 remains Proposed and REV-0034-pending."
    - item: "A-3 uses one shared fail-closed exposure projection without relaxing INV-087/single-flight"
      status: MET
      evidence: "ADR/spec/PKL/WO-0103 consume project_envelope_obligation, RECOVERY_OPEN_STATUSES, and INV-091 with contribution breakdown and cross-consistency pins."
    - item: "External ingress remains a Proposed-only receiver architecture"
      status: MET
      evidence: "ADR-013 requires HMAC/secret authentication, private keyed forwarding, a never-public trading API, D-HOST-1 acceptance, and independent review."
    - item: "Implementation drafts remain gated and independent review is staged"
      status: MET
      evidence: "WO-0102..0104 and PKL remain draft; REV-0034 targets d32dfb1..7fa9985 for the Claude seat."
    - item: "Scope and fresh evidence gates pass"
      status: MET
      evidence: "Scope, PKL, disposition, ledger, install, 17 phase-3 checker tests, anchor greps, residue checks, and git diff checks pass."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  deferred:
    - "Independent REV-0034 result and disposition"
    - "Ameen's post-review ADR text approval"
    - "Fresh signal_records DDL approval at R4"
    - "Runtime implementation and runtime proofs in WO-0102..0104"
  status: VERIFIED
```

Evidence status: **VERIFIED** for the staged docs/spec/queue contract and current anchors.
**UNVERIFIED** by design: independent correctness verdict, ADR acceptance, and future runtime
implementation. **NEEDS-INPUT:** none for WO-0127. **P0:** none observed.
