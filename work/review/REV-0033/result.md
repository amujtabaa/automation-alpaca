---
rev_id: REV-0033
status: COMPLETE
reviewer: Claude (independent review seat; implementer was Codex)
commit_range: 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48
reviewed_at_head: f02775284f4e29d5340f7d6a97fdc19e3636192a (close-out; app/tests verified identical to 9a7af3b)
date: 2026-07-20
verdict: ACCEPT-WITH-CHANGES
---

# REV-0033 — independent review result (WO-0113)

## Verdict

**ACCEPT-WITH-CHANGES.** Every property I probed, mutated, or traced holds on both stores — several
are stronger than the packet required. The two "changes" are small, non-architectural, and do not
put the §5.3 / event-truth / paper-only invariants at risk: one documentation/contract contradiction
(F1) and one narrow, deliberate authentication-fallback window that should either fail closed or be
explicitly pinned and documented (F2). Three further informational notes are for the disposition.
Nothing found blocks the operator's merge decision.

## Verification performed (reproduced, not accepted on the implementer's word)

**Gates (all reproduced locally at `f027752`):** `ruff check` + `ruff format --check` (258 files);
`mypy app/` (64 files clean); `lint-imports` (6 kept / 0 broken); `git diff --check` over the frozen
range (clean); frozen-range diffstat matches (86 paths, 21,655 insertions, 1,321 deletions);
full `pytest -q` exit 0 (one local run; the author's three runs and exact-head CI run #482/#486
green on 3.11+3.12 were independently confirmed via the GitHub Checks API); Codex spec oracle 61/61;
Claude spec oracle 22 passed / 6 documented skips; hardening gates 12/12; scaling gate `passed: true`
(runtime 1.063 ≤ 3.0, startup elapsed 10.009 ≤ 12.0, startup select 9.102 — limits unchanged);
all five AI-OS hygiene checks pass. The Hypothesis `StopTest` teardown diagnostic the request flags
did **not** reproduce in my run — consistent with benign one-off teardown output.

**Fresh reviewer probes (new scenarios, both stores, harnesses in
`work/review/REV-0033/review-notes.md` §P4a):**

- **INV-002 — PASS (29/29 checks).** 200-share position, pre-existing candidate-origin CREATED BUY;
  broker-authoritative 75-share fill on a 50-share locally-terminal SELL → position stays positive
  (125), raw FILL retained, exactly one durable `QUARANTINED`; public listing + new-candidate BUY
  mint refusal + pre-existing BUY final-claim refusal all hold, and **all three consumers re-verified
  after SQLite close/reopen**. A LOCAL-authority excess is rejected with zero mutation (no event, no
  position change).
- **INV-081 — PASS.** The exit epoch closes at **admission**: `create_candidate` itself refuses
  during a working exit ("a same-symbol exit may execute"), the exit drives to flat, the intent
  converges, a genuinely new post-convergence candidate admits and dispatches, and the position does
  not regrow. Both stores.
- **INV-060 — PASS.** With an active grant under HALTED: an ordinary flatten is denied **without
  consuming the grant**; the explicit capability path consumes it exactly once; a grantless
  emergency call is refused outright (`InvalidOrderError`) — stronger than the dedupe I expected.
- **INV-003 — PASS.** Fill persisted, SQLite reopened, exact same-source replay → one FILL,
  position unchanged; same source id with changed price → `status='conflict'` with a **durable**
  `fill_duplicate_conflict` audit ("dropped for manual review", `manual_review_required=True`) and
  zero mutation. (My initial expectation of a raise was wrong; the conflict-result-plus-durable-audit
  contract satisfies the invariant and is what the authored pins assert.)
- **INV-004 — PASS.** Broker-authoritative cumulative 120 on an immutable-100 order: raw sum and
  position retain full venue truth (120), `Order.filled_quantity` caps at 100, explicit `QUARANTINED`
  produced.
- **Cancel/claim recovery-asymmetry probe (self-generated) — fail-closed CONFIRMED.** An open
  recovery raw-attached to a projected-CREATED BUY: flatten signals `buys_open` (the recovery counts
  as buy exposure) and the claim of that BUY is refused on both stores — the concern raised by my
  code-reading pass (see F5 note) does not manifest.

**Mutation checks (guard neutered → exact pin red → in-place restore → green; no checkout, nothing
committed):**

| # | Guard neutered | Exact red observed |
|---|---|---|
| M1 | SQLite shared quarantine reader reduced to FILL-only (`_quarantined_symbols_locked`) | 7 SQLite-node pins red (explicit-quarantine mint gate, claim gate, restart × phase-3b + store-parity corpora); memory green |
| M2 | memory `create_candidate` epoch-admission refusal | `test_candidate_creation_is_refused_during_exit_preemption[memory]` |
| M3 | memory accepted-submit-uncertainty exclusion in `_local_created_cancel_eligible_unlocked` | `test_accepted_direct_sell_cannot_be_canceled_as_local_created[memory]` |
| M4 | envelope accepted-ack fallback producer removed (`record_accepted_submit_uncertainty` call in `app/reconciliation.py`) | `test_envelope_acceptance_double_persist_failure_has_last_write_owner` red across submit/reprice × audit-ok/audit-fails, plus both `test_sqlite_restart_repairs_envelope_acceptance_without_venue_replay` variants |
| M5 | memory flatten regressed to ambient-grant consumption (`override_active = key in active_overrides` for ordinary calls) | `test_ordinary_flatten_cannot_consume_emergency_grant[memory]` |
| M6 | terminal-cleanup source-fill exclusion removed (memory) | `test_terminal_fill_excludes_source_cancels_sibling_and_reconciles_once[memory]` and `test_f2_late_fill_on_terminal_envelope_cancels_created_child[memory]` |

**Cluster deep-reads (five independent read-only passes over the hazard classes; all checks
returned VERIFIED with `file:line` evidence — full reports summarized in `review-notes.md`):**
accepted-submit fallback (5 producers → 2 shared finalizers; consumer sweep found no gate omitting
fallbacks; restart rebuild from persisted events; no second venue call; idempotent replay);
explicit-quarantine projection (single pure projector consuming FILL+QUARANTINED; sibling sweep
found **no remaining FILL-only ADR-001 gate**; producer authority broker-only and atomic; SELL exits
short-circuit before the quarantine gate); emergency capability (explicit-flag flow, precondition
revalidation before reuse, outcome-by-outcome consumption table, no await inside the lock hold,
session binding); exit-epoch/safe-local-cancel/terminal cleanup (admission+dispatch+claim triple
gate; the three independent local-cancel blockers — broker id, open recovery, accepted fallback —
present in both stores; single stand-down helper shared by all callers; line-for-line store parity);
attribution-repair/venue-scope (single marker producer, global dedupe, `ALREADY_APPLIED` guard
against double-decrement, checkpoint never advances past poison, scope written claim→scope→call and
authenticated by every venue-report consumer, restart replays the original rendered scope).

## Findings

### F1 (LOW, doc/contract) — quarantine "clear" path is documented but does not exist
`app/events/projectors.py:152-158` states an overfilled symbol stays quarantined "until an audited
reconciliation/review explicitly clears it." No code path clears an ADR-001 overfill quarantine: the
projection is an unfiltered, append-only, cross-session latch with no resolution event type. The
implementation is **fail-safe and stronger than documented** — but under the repo's own conflict
rule this is a docs/code disagreement on a safety surface. *Failing sequence:* an operator following
the docstring looks for the audited clear flow after remediating an overfill; it does not exist; the
symbol is blocked for the life of the database. *Resolves:* correct the docstring to state the
permanent-latch model (and record the operator's confirmation that latch-forever is the intended
remediation model), or add the audited resolution event; do not weaken the projection by default.

### F2 (LOW, hardening) — scope-authentication degrades in one crash window for dynamic protective SELLs
`app/reconciliation.py:890-898` (`expected_scope is None` fallback in `venue_scope_matches_order`)
plus `app/broker/alpaca_paper.py:218-245` (`allow_dynamic_market_sell`): when a dynamic-venue-type
protective SELL has no current-occurrence `VENUE_ORDER_SCOPE` (reachable in the narrow window of a
crash after a new `SUBMIT_PENDING` occurrence but before the new scope write — the scope map
deliberately refuses the prior occurrence's scope), acknowledgment authentication accepts a broker
LIMIT report carrying **any positive** `limit_price` for that order. Mitigated by scope-before-call
ordering and immutable-identity checks, and a deliberate backward-compat allowance — but it is the
one place where "authenticate against the persisted rendered scope" degrades silently. *Resolves:*
fail closed (route the ack to the uncertainty/recovery path when no current-occurrence scope
exists), or explicitly pin and document the window as an accepted allowance.

### F3 (INFO, cosmetic) — ordinary accepted-submit recovery row born without `client_order_id`
`app/monitoring.py:2567` omits `client_order_id=order.id` where the envelope twin
(`app/reconciliation.py:1435`) and the repair path (`monitoring.py:2663`) pass it. No consumer or
venue-resolution path depends on the field (identity keys on `(local_order_id, broker_order_id)`),
so ownership is unaffected — but it is exactly the sibling-divergence shape this campaign exists to
eliminate. *Resolves:* pass the field for uniformity.

### F4 (INFO, design confirmation) — `FLATTEN_EXISTING` consumes the emergency grant against an in-flight exit
`app/store/memory.py:3444-3452` / `app/store/sqlite.py:4809-4830`: the single-use emergency grant is
consumed when the flatten dedups to a pre-existing in-flight `PROTECTION_FLOOR` exit the emergency
command did not mint. If that exit later dies venue-side unfilled, the position remains held under
HALTED with the grant spent. Recoverable — re-authorization is permitted and revalidates — and
consistent with "one authorized exit existed at consume time," but worth explicit operator
confirmation as intended semantics.

### F5 (INFO, notes for the record)
(a) The claim path's own-venue-uncertainty derivation reads accepted-submit facts but not open
recoveries (`memory.py:3958-3961`); the empirical probe confirms an independent guard refuses the
claim of a recovery-carrying CREATED order anyway (fail-closed holds; see probe above) — a
claim-side mirror of the cancel-path's explicit recovery check would make the defense structural
rather than incidental. (b) `_assert_symbol_envelope_preempted_unlocked` is a memory-only defensive
assertion with no SQLite twin (`memory.py:3435,3505`) — benign asymmetry. (c) The five
`RATIFIED_YES` operator decisions are evidenced by the operator's in-chat relay of the
autonomous-completion mandate, not an in-repo signed artifact; the operator should confirm they
match intent at merge.

## Not independently verified (scope of this review)

- The full 21,655-line diff was reviewed **by property** (five cluster passes + probes + mutations
  + gate reproduction), not line-by-line; the C1–C5 matrices in the WO record were spot-verified
  through those probes/mutations, not re-derived cell-by-cell.
- Branch-coverage percentage (93.50% claimed) and the three-consecutive-full-suite repetition were
  not re-run locally (one full local run exit 0 + exact-head CI on two Python versions were).
- INV-021/022/023/076/091/092/093/094/095 were verified through the authored pin corpora (580
  focused tests reproduced green), the cluster deep-reads of their mechanisms, and the M1–M6
  mutations — not through additional reviewer-authored end-to-end probes beyond those listed above.
- No paper-broker sandbox call was made; all probes use the repo's mock adapter and both local stores.

## Note

Per protocol this verdict does not authorize merging PR #9. The implementer/operator produce
`disposition.md`; F1–F2 are the expected changes, F3–F5 are disposition notes. The merge remains the
operator's explicit action.
