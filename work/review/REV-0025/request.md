---
type: Review Request
rev_id: REV-0025
title: ADR-009 re-review — REV-0024 BLOCK remediation (A-1 clause 6, A-4 invalid budget + rails gate)
status: QUEUED   # flip to AWAITING_REVIEW at dispatch; re-freeze commit_range if the branch merges first
targets: ["ADR-009 (A-1 clause 6, A-4 amendments)", "docs/spec/signal-seat/**", "WO-0102/0104 gating + rails text", "pkl/architecture/signal-seat.md"]
human_gated_surfaces: [order-submission, event-log-vocabulary, schema-migration, transport-boundary]   # A-1 clause 6 adds a launch/transport surface — Ameen-decided 2026-07-14
prior_packet: REV-0024 (verdict BLOCK; F-002/F-003 CLOSED, F-001/F-004 NOT — this packet verifies the two re-remediations)
commit_range: SET-ON-DISPATCH   # branch under active fix — Codex reviews whatever is pushed when pointed at this request; freeze the reviewed SHA in result.md frontmatter
created: 2026-07-14
---

# Review Request REV-0025 — did the re-remediation close REV-0024-F-001 and F-004?

## Your role
You are the **independent review seat** — same protocol as REV-0022/REV-0024 (`AGENTS.md`
"## Review guidelines", `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`): re-derive from the
repo, findings only, do not push fixes. This is a **targeted re-review**: REV-0024 already confirmed
REV-0022's F-002 (atomic conversion) and F-003 (server-owned freshness/classification) are CLOSED —
do **not** re-litigate those unless the new changes regressed them. Your question is narrow: **do the
two human-decided re-remediations close REV-0024-F-001 and F-004 as binding, internally coherent,
implementable text an implementer cannot lawyer around — and did the two propagation fixes (F-003
overview, F-004 WO self-contradiction) actually land everywhere?**

## What changed since your BLOCK (reviewed `413da38` → this range)
Two design decisions were made by the human (Ameen, 2026-07-14) and drafted:

- **REV-0024-F-001 → ADR-009 A-1 clause 6 (backend-owned launch).** The proxy-private-bind guarantee
  is moved off the unobservable app-setting seam onto a backend-owned launch path: `app/server.py::run()`
  (`python -m app`) starts uvicorn programmatically with the bind derived from + re-validated against
  `signal_transport_policy` (exits non-zero before serving on a non-loopback/non-socket bind), and sets
  an `app.state` launch-provenance sentinel the lifespan startup guard requires when the flag is on — so
  a bare `uvicorn app.main:app --host 0.0.0.0` fails startup before serving. Bare-uvicorn deprecated under
  the flag; `04-auth-and-api.md §1` + `pkl` reconciled; WO-0102 gains the launcher/`__main__`/README
  allowed-paths and a **subprocess** bind-failure test asserting pre-serve process failure.
- **REV-0024-F-004 → ADR-009 A-4 (non-refilling invalid budget + rails-presence enablement gate).**
  A per-producer **non-refilling** `signal_invalid_budget_per_epoch` (default 50, tunable `[1, 1000]`,
  hard cap 1000 with startup validation) is debited by **every attributable terminal-at-ingest append**
  — validation `SIGNAL_QUARANTINED`, each novel-hash `SIGNAL_DUPLICATE_CONFLICT`, **and each
  dead-on-arrival `SIGNAL_EXPIRED`** — does not refill while un-quarantined, quarantines on exhaustion,
  and **resets on human release together with the §1 bucket**. The audit-free interim ceiling is
  **withdrawn**; `signal_seat_enabled` is gated on full rails by a **rails-presence startup guard**,
  making live enablement the joint WO-0102+WO-0103+WO-0104 milestone (ingest + atomic conversion + rails).
- **Propagation:** `00-overview.md` + `pkl/architecture/signal-seat.md` now say enforcement is on every
  sensitive route **reads included** (F-003); `03-rails.md` drops the "otherwise-valid" qualifier (rate
  decision before body parse), adds §1a (non-refilling budget), rewrites §2 (enablement gate), §4
  dual-trigger; `WO-0102` withdraws the interim-ceiling/post-quarantine items (moved to WO-0104);
  `WO-0104` gains the invalid budget, the guard lift, and the joint flag-on integration suite.
- **Second-pass fixes folded from the auto-review of the first remediation commit (Ameen-approved,
  same branch):** (a) A-2 atomic conversion is WO-0103's, struck from the WO-0102 milestone; live
  enablement co-gates on WO-0103 too. (b) dead-on-arrival `SIGNAL_EXPIRED` now debits the budget
  (a paced just-expired flood otherwise evaded it). (c) `PRODUCER_RELEASED` resets the §1a budget as
  well as the §1 bucket (else release is inert). (d) the exact final-slot transition is pinned (the
  debiting append completes normally; the epoch opens on the next ingest). (e) the budget hard cap is
  numeric (`1000`) with startup validation. (f) the Option-E finite-volume claim is narrowed —
  legitimate accepted-signal volume is rate-bounded, not finite over indefinite time (no false
  globally-finite-storage promise). These are refinements to the same amendment, not new design.
- **Third-pass fixes (Ameen-approved, same branch):** (a) **the launch-provenance guard is now
  enforced at request time, not only lifespan startup** — `uvicorn app.main:app --host 0.0.0.0
  --lifespan off` skipped the lifespan guard and served the flag-on app on a network bind; a
  fail-closed ASGI request guard (503 when the sentinel is absent) closes that bypass, and the
  subprocess test now covers `--lifespan off`. (b) `SIGNAL_EXPIRED`/`SIGNAL_QUARANTINED`/
  `SIGNAL_REJECTED` now carry `(producer_id, signal_id)`/`record_id` so replay folds to the right
  record (multi-pending-expiry replay test added). (c) the §4 normative-order debit rule now includes
  dead-on-arrival expiry. (d) WO-0102's isolation tests get a sanctioned fixture that sets the launch
  sentinel through the real seam (no guard-weakening bypass). (e) budget config changes are
  cycle-scoped/pinned so a mid-cycle redeploy can't silently alter the bound.

## Questions to answer
1. **F-001 closed?** Is the backend-owned launch path an *enforceable* seam — can a bare
   `uvicorn app.main:app --host 0.0.0.0` (or any non-loopback bind) actually be made to fail before
   serving, given the sentinel + programmatic-launch design? Is the flag-off posture (bare uvicorn keeps
   working) acceptably bounded? Is anything about the sentinel spoofable by an attacker who controls the
   process environment but not the code?
2. **F-004 closed?** Does the non-refilling invalid/conflict budget make the append-only log **finite
   under indefinitely-paced hostility at or below the refill rate** (the exact probe that broke the
   refilling-bucket-only design)? Is "resets only on human release" airtight — no refill path, no
   silent reset? Does the rails-presence startup guard actually make an unrailed enabled endpoint
   unconstructible, or is it still discipline dressed as a guard?
3. **Propagation complete?** Is the reads-included enforcement now consistent across ADR/overview/
   §1a/pkl (no surviving "mutating command routes" narrowing)? Is the WO-0102 epoch-ownership
   self-contradiction gone, and is the interim ceiling withdrawn everywhere (no `signal_ingest_ceiling_*`,
   no zero-append flood test left as WO-0102 behavior)?
4. **Coherence / regressions:** do the new clauses contradict each other, the unamended ADR body, the
   spec, the as-built seams (`app/main.py` `create_app`/lifespan, the `python -m app` launch, the
   `_atomic` snapshot), or the still-CLOSED A-2/A-3? Does gating enablement on the joint milestone leave
   any WO-0102 required test unrunnable without being explicitly labelled a joint-milestone test?

## Where to look
- `docs/adr/ADR-009-signal-seat-boundary.md` §Amendments A-1 (clause 6) + A-4 (the review target).
- `work/review/REV-0024/result.md` — your own findings and the closure criteria.
- `docs/spec/signal-seat/00,03,04` + `02` note; `pkl/architecture/signal-seat.md`.
- `work/queue/WO-0102`, `WO-0104` — whether the test contracts carry the re-remediation.
- `app/main.py` (`create_app`, lifespan, module-level `app`), `README.md` launch command.

## Verdict vocabulary
`ACCEPT` | `ACCEPT-WITH-CHANGES` (enumerate) | `BLOCK` (enumerate). Write findings to
`work/review/REV-0025/result.md`; Ameen dispositions in `disposition.md`. An ACCEPT/
ACCEPT-WITH-CHANGES here clears the gate REV-0022 opened and REV-0024 kept: ADR-009 may then be
marked Accepted by Ameen and WO-0102..0104 unfreeze per the joint-enablement sequencing.
