# AUDIT-0001 — Root-cause audit of the session's fixes + the quarantine treadmill

Date: 2026-07-15 · Directive: Ameen — "ensure your fixes in this entire session's
development effort were root cause fixes and not simple patches… find remaining
issues proactively and root-cause the quarantine treadmill."
Method: three tiered agents (fix-audit/sonnet, treadmill-map/opus,
same-class-hunt/sonnet), every acted-on claim re-verified by the implementer
against tip. Raw agent transcripts in the session log; verified deltas shipped
as WO-0035; gated roots drafted as WO-0036.

## 1. Verdicts on this session's fixes (symptom vs root)

| Fix | Verdict at audit | Root disposition NOW |
|---|---|---|
| WO-0032 per-symbol single-ACTIVE | **PARTIAL** — correct invariant, but a backstop over the unlinked SellIntent↔Envelope lifecycle; the orphan (ACTIVE envelope, EXPIRED intent) still forms at session close | Root = R2, **gated** → WO-0036 (options for Ameen) |
| WO-0034 concurrency-0 `prior_position` | **PATCH** (caller-burden param) — the same defect was LIVE on the reconcile inferred-fill path | **ROOT-FIXED** in WO-0035/F3: `append_fill` self-derives the pre-fill position (own-dedupe-key exclusion); param deleted; class dead |
| WO-0033 parity-0 `now=now` at one call site | **PARTIAL** — the store methods had no clock params at all; 4 tick transition sites + fill folds stayed wall-clock | **ROOT-FIXED** in WO-0035/F1 at the store surface (now= + lifecycle-event ts); tick-side threading queued (mechanical) |
| WO-0033 parity-1 session-ensure ordering | **ROOT for its site**; audit found the DEEPER shape: nested-tx CRASH in approve/resume on date rollover | **ROOT-FIXED** in WO-0035/F2 (pre-tx validate + bootstrap, memory-parity ordering, C2 guard pinned) |
| WO-0034 spec-1 redrive-refusal eventing | **PARTIAL** — the venue leg still dropped broker rejection reasons | **ROOT-FIXED** in WO-0035/S1 (`envelope_venue_rejected/_released` durable events) |
| WO-0031 tranche latch (WORKING-only fold) | **ROOT-CAUSE** — every history fold checked filters provenance correctly; no sibling found | Closed |
| pure-math-0 deviation band | Root for its finding; its first cut SHADOWED the floor rail (caught by the WO-0021 pin) → precedence pinned (floor outranks band) | Closed + lesson recorded |

## 2. The treadmill, root-caused

The defensive states fall into three classes. **(a) External reality** —
TIMEOUT_QUARANTINE entries, genuine BREACHED, recovery-ledger escalations:
correct permanent design, NOT treadmill. **(b) Internal design gaps** and
**(c) defenses feeding defenses** — the treadmill. The (b)/(c) traffic
clusters onto few roots, and the meta-root is ONE pattern:

> **The same truth derived independently in two places, then defended when
> the derivations disagree.**

| Root | Status |
|---|---|
| R3 position/remaining folded twice (record-first bridge vs append_fill) | **CLOSED at the check** (WO-0035/F3 self-derivation). The larger consolidation (envelope remaining projected from the FILL log instead of a second fold) is W4 architecture, gated, noted in WO-0036's context |
| R2 SellIntent↔Envelope lifecycle unlinked | **OPEN, gated** → WO-0036 (the per-symbol guard contains the blast; the orphan remains) |
| R5 session-ensure side effects in read/validate paths | **CLOSED for the found sites** (parity-1 + F2); convention queued: entity-validate before session-bootstrap, bootstrap never inside the main tx |
| R4 clock-discipline leaks | **CLOSED at the store surface** (F1); caller threading queued |
| R6 terminal-write-then-best-effort-cancel, never reconciled | **OPEN, gated** → WO-0036 (cancel convergence arm) |
| R1 plan/write double-validation as "dominant root" (opus agent) | **CORRECTED by the implementer**: the agent cited pre-WO-0025 code via a stale Phase-A finding doc. At tip the working-order predicate is live-derived (policy.py `_live_working_order_id`), the multileg livelock is fixed and pinned, and benign world-movement lands in the evented no-freeze STAGE_REFUSED_STALE path. D-3's two checks are ADR-mandated defense-in-depth (the write-time check is the last line before the venue, under the lock); re-planning inside the store lock would couple the pure policy to the store for marginal gain. **Considered and rejected — recorded per the conflict rule.** |

## 3. Proactive finds (new, verified, fixed)

- **F2 — reproduced P1 crash**: first envelope approval/resume of a new
  calendar day crashed SqliteStateStore (nested BEGIN). Every same-day test
  initialize() hid it. Fixed + pinned (WO-0035).
- **F3 — live sibling of concurrency-0** on the reconcile inferred-fill path.
  Root-fixed for the whole class (WO-0035).
- Full same-class sweep results (clock fallbacks C1, ensure-ordering C2,
  poisonous-optional C3, guard-scope C4, provenance-fold C5, caller-burden C6):
  C3/C5 clean; C4 partially swept (unverified remainder queued); C1/C2/C6
  produced the F1/F2/F3 fixes above.

## 4. What remains for a human

1. **WO-0036** (R2 + R6) — the two gated roots, options drafted.
2. W4 architecture note: single-fold consolidation of envelope remaining
   (R3's full form) belongs in the W4 design pass, not a patch.
3. The queued mechanical follow-ups listed in WO-0035.
