---
type: Review Request
rev_id: REV-0028
title: WO-0036 R2 — SellIntent↔Envelope structural lifecycle link (gated surfaces + ADR-010 §8 amendment)
status: AWAITING_REVIEW
targets: [WO-0036]
human_gated_surfaces: [order-intent lifecycle, session-close event truth, cancel/replace, manual flatten]
review_branch: claude/sellintent-envelope-linking-h2z7i7
base_sha: 22617f4                        # tip before this pass (WO-0036 cluster 4)
gated_fix_commits: [f022f59, bedf7e4]    # the R2 link + the fresh-eyes follow-up
env: python 3.12                 # ruff/mypy/pytest pinned by constraints.txt
created: 2026-07-15
---

# Review Request REV-0028 — the SellIntent↔Envelope lifecycle link (WO-0036 R2)

## Your role
Independent review seat (a different model from the author). Re-derive from the code,
don't rubber-stamp, findings only — do not push fixes. The change is commit `f022f59`
on branch `claude/sellintent-envelope-linking-h2z7i7`; `git show f022f59 -- app` is the
whole engine-side change. Success criterion set by the operator: **zero novel P1/P2
findings** proves the lifecycle-inconsistency class is closed at the root.

## What you're reviewing

WO-0036 R2 ("Option A+", ADR-010 §8): the SellIntent and ExecutionEnvelope lifecycles are
now structurally linked at write choke points, both stores, no new stored derived truth.
Mechanism summary (full semantics in `docs/adr/ADR-010-execution-envelope.md` §8 and
`docs/INVARIANTS.md` INV-090; every claim pinned in
`tests/test_wo0036_r2_lifecycle_link.py`, both stores):

1. **Activation link** — every entry into ACTIVE (approve + generic transition, first
   activation and resume) validates the backing intent (exists / symbol-match /
   pending-or-approved) and normalizes PENDING→APPROVED atomically.
2. **Terminal release, two choke points, one rule** — the intent expires when the
   mandate's LAST live obligation ends: at a releasing terminal (not SUPERSEDED) when no
   other live envelope and no possibly-live child remains, else at that child's venue
   terminal (the child-terminal hook in the order-transition apply points).
3. **Close-side spare** — session close spares live-envelope-backed intents; the close
   event payload gains `spared_sell_intents`.
4. **Flatten link** — deferral to a live/quarantined envelope child; the preemption
   helper never CANCELs an envelope under a possibly-live child; single terminal
   transition per intent.
5. **Exclusive driver** — legacy dispatch + public intent transition refuse a
   live-envelope-backed intent.
6. **INV-087 amendment** — the per-symbol clash counts FROZEN as live.

## Decisions at this gate — RESOLVED

Resolved by Ameen 2026-07-15 (session directive delegating the REV-0028 decisions to the
author's recommendation). The reviewer VERIFIES these, it does not re-decide them:

- **Option-A+ divergence — RATIFIED.** The WO's original recommendation was "activation
  transitions the intent APPROVED→ORDERED". The implementation keeps the intent
  APPROVED-while-owned instead — `sell_intent_is_active` keys an ORDERED intent on its
  ONE linked order, which an envelope does not have, so ORDERED-with-no-order would read
  *inactive while the envelope works* (re-opening duplicate protection) and arm the
  legacy "ORDERED but has no linked order" trap. Rationale recorded in ADR-010 §8;
  probe it — if the reviewer finds the rationale unsound, that IS a finding.
- **R6 convergence wording — ACCEPTED as satisfying the done-when's intent.** The WO
  described "N retries → recovery-ledger escalation"; the shipped mechanism is per-tick
  idempotent re-drive with logged failure (`_converge_expired_envelope_cancels`) — the
  arm never stops trying, so nothing is silently stranded (the wording's substance).
  Probe: is there any input on which the re-drive arm stops trying without the order
  reaching a terminal/CANCEL_PENDING state?

## Author's post-landing fresh-eyes pass (2026-07-15) — findings, all fixed (commit bedf7e4)

Disclosed so the packet is a complete account (verify the fixes, and treat any FURTHER
instance of these classes as novel):

- **R-1 (release predicate, masked predecessor):** `_envelope_has_live_child_*` first
  keyed on the single newest working order; a staged CREATED reprice replacement masked
  a still-SUBMITTED predecessor → the terminal release read "no live child" and expired
  the intent while the predecessor rested (double-book window), and the flatten
  preemption could CANCEL the envelope under it. Fixed with an every-child
  venue-liveness scan; pinned `test_c7_staged_replacement_never_masks_a_live_predecessor`.
- **R-2 (same class, supersession choke point):** WO-0027 rule (i)'s live-order block
  evaluated the same newest-wins view → an amendment could activate a successor next to
  the masked resting predecessor (INV-077 double exposure). Fixed with a store-side
  every-child belt in both stores; pinned
  `test_c8_supersede_refused_while_a_masked_predecessor_rests`; ADR-010 §3 amended.
- **F-3 (pre-existing suite time bomb, not an engine defect):** three tape-driven test
  files activated envelopes with wall-clock `activated_at` while feeding NOW-anchored
  tapes — the policy's since-activation window (INV-086) empties once wall UTC passes
  the tape anchors, so 12 tests were green in morning runs and permanently red from
  2026-07-15 ~13:20 UTC (verified failing at the pre-R2 base 22617f4). Fixtures now
  activate through the `now=`-threaded transitions
  (`tests/store_helpers.activate_envelope_at`) — fully injected-clock. The engine
  behavior (window keyed to THIS mandate's activation) is correct and unchanged.

## Known accepted behaviors (disclosed, not defects — challenge if you disagree)

- **Monitoring's `_envelope_working_order` stays newest-wins**: the EXPIRED
  cancel-convergence arm and the stale-data CANCEL disposition may need one extra tick
  when a staged CREATED replacement masks a live predecessor (first pass cancels the
  CREATED child locally; the next pass sees the predecessor and re-drives its venue
  cancel). Converges, never strands; left as-is deliberately — the store-side rails
  above are the exposure-preventing layer.
- **Emergency reduce under HALTED with a resting envelope child defers** (evented) —
  the alternative (preempt + fresh MARKET sell) double-books the resting child. The
  operator's path to a hard exit: cancel the child via the order-cancel route, then
  flatten. The deferral event carries the child's order id and status for exactly that.

## Probes (suggested, not exhaustive — re-derive your own)

- Any path that mints or resumes an ACTIVE envelope without the intent link (supersession
  relies on the planner's same-intent+symbol validation + the inductive invariant — is
  that sound?). Any writer that terminalizes an intent while a live envelope backs it.
- Release timing: can the symbol re-open (dedup release) while ANY venue exposure for the
  old mandate still exists? Quarantined child at every point. CANCEL_PENDING late fills.
- Close-boundary: spared intent's day-1 `session_id` means day-2 closes never consider
  it — is envelope/child-terminal release provably the only remaining exit for it?
- Flatten: every branch (FLAT / EXISTING / SUPERSEDE_AND_CREATE) against staged CREATED,
  SUBMITTING, SUBMITTED, quarantined, and predecessor-live children; double-expiry of the
  superseded intent; HALTED + override interactions.
- Dual-store parity: event order and payloads of the new writes
  (`sell_intent_transition` reason=envelope_activation/envelope_terminal,
  `envelope_preemption_deferred`, `spared_sell_intents`).

## Invariants added or amended since REV-0023 (protocol §"invariant delta")
- **INV-090** (new) — the lifecycle link (statement above).
- **INV-087** (amended) — LIVE = ACTIVE|FROZEN; demoted to defense-in-depth behind the link.
