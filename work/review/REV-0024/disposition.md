---
type: Review Disposition
rev_id: REV-0024
verdict_received: BLOCK
disposition_status: REMEDIATION_DRAFTED   # Ameen's F-001/F-004 decisions captured; A-1/A-4 re-remediated; queued for REV-0025
reviewed_commit: 413da3813191fe31fabf51e9a7247670a45ec561
reviewer_model: GPT-5 Codex
next_packet: REV-0025
date: 2026-07-14
---

# Disposition — REV-0024 (ADR-009 A-1..A-4 remediation re-review)

**Verdict: BLOCK** (GPT-5 Codex, staged packet, reviewed frozen commit `413da38`, result
`result.md` pushed 2026-07-14). This packet existed to verify that amendments A-1..A-4 closed the
four REV-0022 P1s. **Two of four are now closed; two are not, and the re-review surfaced two new
propagation contradictions.** ADR-009 acceptance and WO-0102..0104 activation remain **gated** —
unchanged from REV-0022.

## Closure scorecard (against REV-0022)

| REV-0022 finding | A-N remediation | Codex verdict |
|---|---|---|
| F-001 — credential/transport/read boundary | A-1 | **NOT closed** — lifecycle/actor/read-matrix/docs/flag-off now specified, but the *actual-bind* guarantee is not enforceable through the stated ASGI seam, and the overview still narrows enforcement to mutating routes |
| F-002 — atomic approval→intent conversion | A-2 | **CLOSED** — one dual-store atomic command, one lock/txn, no-await rule, signal state in the memory snapshot, all-or-nothing, idempotent retry, crash/interleave matrix; split-await facade explicitly forbidden |
| F-003 — server-owned freshness + classification | A-3 | **CLOSED** — deadline formula, skew bounds, hard TTL cap, injected clock, restart-stable persisted deadline, conversion-time re-check, exactly-once exposure formula (ORDERED not double-counted); INV-7 asymmetry preserved |
| F-004 — finite audit / backpressure | A-4 | **NOT closed** — post-quarantine + interim-ceiling paths are constant-row, but paced invalid/conflict traffic **at or below the refill rate** never opens a quarantine epoch and appends one audit event forever; staged WO contract also self-contradicts on which wave owns epochs |

## The four REV-0024 findings

- **REV-0024-F-001 (P1) — the actual-bind guard is not enforceable through the bounded seam.**
  A-1 requires startup to verify the *real* listener and fail on any non-loopback/non-socket bind.
  But the as-built launch path is `uvicorn app.main:app --host …`; uvicorn owns `--host`/`--uds`
  outside the app, and an ASGI lifespan scope cannot observe the bind address (it appears only on
  per-request HTTP scopes, after startup). An app-setting check can be green while the process is
  actually launched on `0.0.0.0`. **→ genuine design decision (below).**

- **REV-0024-F-002 (P1) — paced hostile traffic appends to the execution log without bound.**
  A rate bound is not a storage bound. At exactly the refill rate (probe: 1 req/min for 7 days →
  10080 `SIGNAL_QUARANTINED`/`SIGNAL_DUPLICATE_CONFLICT` events, bucket never below 9 tokens,
  quarantine never opened), the append-only log grows forever. This is REV-0022 F-004's failure
  class, and it also undercuts A-2's Option-E deferral premise (that A-4 makes signal volume
  finite). **→ genuine design decision (below).**

- **REV-0024-F-003 (P1) — overview text still contradicts the reads-included boundary.**
  `docs/spec/signal-seat/00-overview.md:33-41` still says flag-on enforces the operator credential
  only on **mutating command routes**; A-1 and `04-auth-and-api.md` require it on **every sensitive
  route, reads included**. The overview declares every ADR/spec disagreement a defect — so this is
  self-flagged. **→ propagation fix (wordsmith the overview to reads-included + point at the
  fail-closed mounted-route matrix). Not a design decision.**

- **REV-0024-F-004 (P1) — WO-0102 self-contradicts on epoch ownership + an "otherwise-valid"
  qualifier invites parse-before-rate-decision.** WO-0102:75/:79 say its interim ceiling is
  audit-free and the `PRODUCER_QUARANTINED`/`PRODUCER_RELEASED` epoch machinery is WO-0104's, yet
  :78 still requires post-quarantine handling + coalesced audit *in WO-0102*. Separately,
  `03-rails.md:16-19` says breach occurs at an "otherwise-valid ingest", which cannot be known
  before the mandated no-body rails decision (auth → rails → capped read → parse). **→ propagation
  fix (remove/relabel :78 as a WO-0104 acceptance test; define bucket debit on every authenticated
  request before body read, no parse-validity qualifier). Not a design decision.**

## Split: two human design decisions vs. two propagation fixes

The block resolves along a clean seam. Per the standing hold ("no more spec edits until the staged
review lands"), **nothing below is done yet** — recorded here for Ameen's disposition:

1. **F-001 — where does bind enforcement live?** The app-setting-only guard is genuinely
   insufficient. Options: (a) a backend-owned programmatic launch entrypoint whose bind comes from
   the validated setting, with the direct `uvicorn app.main:app` path forbidden/deprecated when the
   seat is enabled, proven by a subprocess test that attempts `0.0.0.0` and observes startup
   failure *before* requests are served; or (b) an equally enforceable process-manager/deployment
   control declared as the boundary. This changes WO-0102 scope (adds a launcher + docs path) —
   **human-gated, ADR-amendment territory.**

2. **F-004 — the finite invalid/conflict budget.** Needs a per-producer invalid/conflict budget
   that does **not** refill within an open epoch and forces quarantine after a bounded total (or
   moves attributable rejection detail out of the append-only log after N events). This is the same
   class I flagged pre-review: gating `signal_seat_enabled` on WO-0104's full rails would collapse
   the interim-ceiling flood window entirely — worth deciding alongside this. **Human-gated design
   choice.**

3. **F-003 + F-004 propagation fixes** (overview reads-included; WO-0102 epoch-ownership +
   "otherwise-valid" removal) are mechanical reconciliations of already-decided amendment text.
   They are low-risk, but they still touch spec that feeds a human-gated surface, so I am **holding
   them for the same batch** rather than patching reactively — consistent with the "don't converge
   by inline patching" lesson.

## What is NOT being done in this disposition (explicit)

- ADR-009 stays **Proposed** (acceptance still rescinded). Not marking Accepted.
- WO-0102..0104 stay **RE-GATED**. Not unfreezing.
- No inline PR review comments patched — the staged `result.md` is the authority; the block is
  addressed as one batch after Ameen's two decisions, not comment-by-comment.

## Human decisions (Ameen, 2026-07-14) and the re-remediation drafted from them

Ameen made both design decisions:

1. **F-001 → backend-owned launch path.** Add a backend-owned entrypoint (`app/server.py` /
   `python -m app`) that starts uvicorn programmatically with the bind derived from and re-validated
   against `signal_transport_policy`, plus a lifespan launch-provenance sentinel so a bare
   `uvicorn app.main:app --host 0.0.0.0` fails startup before serving. Bare-uvicorn deprecated under
   the flag; proven by a subprocess bind-failure test. **Drafted into ADR-009 A-1 clause 6.**
2. **F-004 → non-refilling invalid budget + gate the flag on full rails.** Add a per-producer
   non-refilling `signal_invalid_budget_per_epoch` (default 50) debited by every attributable-
   rejection append (validation quarantine + novel-hash conflict), which does not refill while
   un-quarantined, quarantines on exhaustion, and resets only on human release. Withdraw the
   audit-free interim ceiling; gate `signal_seat_enabled` on full rails via a rails-presence startup
   guard (no unrailed window). **Drafted into ADR-009 A-4.**

Both are defensive-security surface work (transport/bind, rate-limit/quarantine) — authored on the
current Opus model per the repo-primer routing preference.

### Re-remediation change set (drafted 2026-07-14, PROPOSED — pending REV-0025)

- `docs/adr/ADR-009-signal-seat-boundary.md`: A-1 clause 6 (backend-owned launch); A-4 non-refilling
  invalid/conflict budget + rails-presence enablement gate + interim-ceiling withdrawal; body §Contract
  reconciled; ingest-order dual-trigger.
- **F-003 propagation:** `00-overview.md` + `pkl/architecture/signal-seat.md` now say enforcement is
  on **every sensitive route, reads included** (not "mutating command routes"), pointing at the §1a
  fail-closed matrix.
- **F-004 propagation:** `03-rails.md` §1 "otherwise-valid" qualifier removed (rate decision before
  body parse); §1a non-refilling budget added; §2 rewritten as the enablement gate; §4 dual-trigger.
  `WO-0102` interim-ceiling + post-quarantine items withdrawn/relabelled to WO-0104; backend-owned
  launch + subprocess test + allowed_paths (launcher, README) added; rails-presence guard + joint
  enablement milestone. `WO-0104` gains the non-refilling budget, the rails-presence guard lift, and
  the joint flag-on integration suite.
- `04-auth-and-api.md` §1 backend-owned launch seam; `02-lifecycle.md` quarantine dual-trigger note.

## Path to clearing the gate

**REV-0025** re-reviews this re-remediation (`request.md` staged). The gate clears only on an
ACCEPT / ACCEPT-WITH-CHANGES disposition of REV-0025 — at which point ADR-009 may be marked Accepted
by Ameen and WO-0102..0104 unfreeze per the joint-enablement sequencing. ADR-009 stays **Proposed**
and the WOs stay **RE-GATED** until then.
