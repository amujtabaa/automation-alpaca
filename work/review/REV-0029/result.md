# REV-0029 — Independent Cross-Model Review Result

**Reviewer:** Codex (independent review seat; builder was Claude)
**Review date:** 2026-07-18
**Pinned branch/SHA:** `consolidate/r2-canonical` at
`f82d953051bbc88b7668fee1cc02af3f9bf31b51`
**Diff reviewed:** `5d10c70..f82d953` (23 commits; 53 files)
**Amended:** 2026-07-18 after a fresh adversarial self-audit, before builder disposition

## Verdict

**BLOCK**

The shared obligation projection and the atomic session-close implementation close substantial
parts of the R2 treadmill, and the Codex-oracle reseed is legitimate. The branch nevertheless has
three independently reproduced execution-safety classes: flatten can submit beside a
venue-uncertain BUY, an approved BUY handoff can cross both direct exit mint paths, and
`needs_review` can authorize a second SELL. All reproduce in both stores on human-gated execution
surfaces. In addition, one new safety test cannot exercise the behavior it claims to pin, and the
advertised CI-form green gate is not reproducible from the pinned clean checkout.

No source, test, or documentation file was changed during this review. Suggested correction
shapes below are proposals only.

## Findings

### P0-1 — Option B treats a cancellation request as convergence and can submit a flatten SELL beside a venue-live BUY

**Concrete failure.** Begin with a locally held 100-share position and a 40-share BUY. A temporary
public-store probe drove the BUY through each sibling status and then called the ordinary flatten
and claim APIs. Both stores produced the same result:

```text
memory/submitting:          flatten=created; sell_qty=100; sell_claim=claimed
sqlite/submitting:          flatten=created; sell_qty=100; sell_claim=claimed
memory/cancel_pending:      flatten=created; sell_qty=100; sell_claim=claimed
sqlite/cancel_pending:      flatten=created; sell_qty=100; sell_claim=claimed
memory/timeout_quarantine:  flatten=created; sell_qty=100; sell_claim=claimed
sqlite/timeout_quarantine:  flatten=created; sell_qty=100; sell_claim=claimed
```

For the normal Option B schedule, the initial BUY is `SUBMITTED`, the store correctly returns
`FLATTEN_BUYS_OPEN`, and the caller asks the broker to cancel it. The local transition is only to
`CANCEL_PENDING` (`app/monitoring.py:240-278`). The immediate retry no longer sees the BUY, so it
mints a full-size SELL; claim then moves that SELL to `SUBMITTING`. The BUY can still late-fill,
which leaves/reopens a 40-share position after the SELL or overlaps both sides at the venue.

**Root cause and reachability.**

- `OPEN_BUY_STATUSES` contains only `CREATED`, `SUBMITTED`, and `PARTIALLY_FILLED`
  (`app/store/core.py:765-776`). The caller's cancellation set is exactly that same incomplete set
  (`app/monitoring.py:240-247`). Equality proves agreement, not a safe postcondition.
- `CANCEL_PENDING` is nonterminal and accepts late fills (`app/transitions.py:147-150`). Existing
  pins `test_cancel_pending_keeps_polling_and_records_late_fill` and
  `test_cancel_pending_late_fill_can_complete_the_order` prove that schedule.
- `SUBMITTING` is an open submission claim whose broker call may be pending or in flight, and
  `TIMEOUT_QUARANTINE` explicitly means the order may already be live or filled
  (`app/models.py:225-248`). Treating either as absent violates the safety core's ambiguity posture
  (`CLAUDE.md:34-43`).
- The new positive test actually asserts the unsafe intermediate state: after cancel/retry there is
  one SELL while the BUY remains `CANCEL_PENDING`
  (`tests/test_wo0036_r2_flatten_buys_open.py:164-182`). Its mock broker marks the broker side
  canceled immediately, so it cannot exercise the documented late-fill model.
- ADR-010 acknowledges only `SUBMITTING`/`TIMEOUT_QUARANTINE` as exclusions and calls the retry
  bounded/fail-closed, but omits `CANCEL_PENDING` (`docs/adr/ADR-010-execution-envelope.md:140-155`).
  INV-081 makes the same incomplete claim (`docs/INVARIANTS.md:582-599`).

The one-lock store decision is otherwise real: memory `app/store/memory.py:2538-2684` and SQLite
`app/store/sqlite.py:3800-3965` read position, project the declared BUY set, decide, and mint with no
intervening await. The emergency override also survives a `FLATTEN_BUYS_OPEN` return. Those facts do
not close the sibling-status property.

**What resolves it.** Separate “cancellable by this helper” from “blocks flatten because venue
execution is possible,” and do not mint until every blocking BUY is broker-authoritatively terminal
or otherwise reconciled. A correction should have this shape, not blindly cancel ambiguous orders:

```diff
- OPEN_BUY_STATUSES = {CREATED, SUBMITTED, PARTIALLY_FILLED}
+ CANCELLABLE_BUY_STATUSES = {CREATED, SUBMITTED, PARTIALLY_FILLED}
+ FLATTEN_BLOCKING_BUY_STATUSES = CANCELLABLE_BUY_STATUSES | {
+     SUBMITTING, CANCEL_PENDING, TIMEOUT_QUARANTINE,
+ }
```

Then pin every nonterminal BUY status, cancel/claim interleavings, late fills, bounded failure, and
override survival in both stores. Because a fresh BUY can appear after a flatten SELL is minted,
the final submission claim also needs a symmetric cross-side, same-symbol revalidation.

### P0-2 — An approved BUY handoff can cross both exit mint paths and both orders reach broker submission

This is independent of P0-1's incomplete status set. Even a blocking set containing every
nonterminal Order status cannot see an approved Candidate that has not produced its BUY order yet.

**Concrete route-reachable failure.** Begin with a held 100-share AAPL position. Approve a fresh
40-share BUY Candidate, then pause at the real facade's await boundary between
`gate.approve(candidate_id)` and `create_order_for_candidate(...)`
(`app/facade/store_backed.py:782-785`). While the Candidate is durably `APPROVED` but has no Order,
run either manual flatten or the ordinary autonomous protection-open sequence. Resume Candidate
dispatch, then run the normal pending-order submission sweep during the regular session. Temporary
public-store/engine probes made real mock-adapter submission calls and produced:

```text
memory/manual:     broker_sides=['sell', 'buy']; sell=submitted; buy=submitted
sqlite/manual:     broker_sides=['sell', 'buy']; sell=submitted; buy=submitted
memory/protection: broker_sides=['sell', 'buy']; sell=submitted; buy=submitted
sqlite/protection: broker_sides=['sell', 'buy']; sell=submitted; buy=submitted
```

A second probe minted the manual-flatten SELL first and created a fresh BUY afterward. In both
stores, both `SELL -> BUY` and `BUY -> SELL` claim orderings returned `claimed` twice and left both
orders `SUBMITTING`. Thus the defect is not dependent on insertion order or the particular facade
pause above.

**Root cause and reachability.**

- Option B scans only existing BUY Order rows under the flatten lock
  (`app/store/memory.py:2661-2667`; `app/store/sqlite.py:3938-3947`). The Candidate that the normal
  approval route has already authorized is invisible.
- The protection path cancels the BUYs it observed, then awaits and separately calls
  `open_protection_exit` (`app/monitoring.py:360-410`). Neither store's atomic protection-open
  operation rechecks BUY Orders or approved Candidates (`app/store/memory.py:2320-2412`;
  `app/store/sqlite.py:3562-3655`).
- Candidate dispatch rechecks controls, risk, and quarantine but not a same-symbol direct/envelope
  exit obligation (`app/store/memory.py:2892-2960`; `app/store/sqlite.py:4206-4301`).
- The final claim choke handles envelope/direct SELL siblings and control state, but has no
  cross-side same-symbol rail (`app/store/memory.py:2962-3185`;
  `app/store/sqlite.py:4303-4555`; `app/store/core.py:2391-2511`). The ordinary sweep then calls the
  adapter once per successful claim (`app/monitoring.py:1161-1232`).

**Wrong outcome.** The SELL can close the original 100 shares while the BUY fills 40 shares beside
or after it, self-crossing/re-growing the position that manual flatten or protection was supposed
to exit. This is an order-submission safety-surface defect, not merely a stale UI outcome.

**What resolves it.** Define and enforce one same-symbol cross-side eligibility property at the
final claim in both stores, with the exit taking precedence only after every possibly executable
BUY is authoritatively terminal. Also close the Candidate handoff: flatten/protection must either
atomically stand down PENDING/APPROVED BUY Candidates for the symbol or Candidate dispatch must
refuse while a direct/envelope exit obligation exists. The correction needs this shape (proposal
only; exact policy and audit event require the builder's disposition):

```diff
+ if claiming BUY and same_symbol_exit_may_execute(order.symbol):
+     return CLAIM_BLOCKED("same-symbol exit obligation exists")
+ if claiming SELL and same_symbol_buy_may_execute(order.symbol):
+     return CLAIM_BLOCKED("same-symbol BUY may execute")
+ if dispatching approved Candidate and same_symbol_exit_may_execute(candidate.symbol):
+     refuse_or_hold_dispatch_with_audit()
```

`same_symbol_buy_may_execute` must include open claims, broker-working intervals,
`CANCEL_PENDING`, and `TIMEOUT_QUARANTINE`; it must never blindly cancel ambiguity. Pin the real
approval pause, post-mint BUY creation, both claim orderings, manual/protection exits, and the full
submission sweep in both stores. Fixing only the flatten mint decision leaves the demonstrated
post-mint schedule open.

### P0-3 — `needs_review` does not quarantine the sell side; two second-SELL lanes reach `SUBMITTING`

This falsifies the P-B safety posture, ADR-010, INV-090, and plan §6 OBS-2.

**Lane A — same active envelope.** With local position 100, an active envelope stages and claims
SELL `O1`. `O1` becomes locally `CANCELED`, while recovery latches `needs_review` because broker
fills exist and are not yet in event truth. After cooldown the same envelope stages and claims
SELL `O2` for 100:

```text
memory: first=claimed; second_stage=staged; second_claim=claimed; second_status=submitting
sqlite: first=claimed; second_stage=staged; second_claim=claimed; second_status=submitting
```

The shared projector collects the `needs_review` child but deliberately excludes it from unresolved
children (`app/store/core.py:1458-1466`). Stage checks ambiguity, unresolved recovery, uncertain
claim, and unresolved-child count, but never `needs_review_child_order_ids`
(`app/store/memory.py:1923-1934`; `app/store/sqlite.py:3062-3079`). The final claim has the same
omission (`app/store/memory.py:3025-3054`; `app/store/sqlite.py:4377-4412`).

**Lane B — direct SELL followed by a fresh owner.** A direct SELL `O1` is submitted, then recovery
records broker fills as `needs_review` without inventing local fills. X-003 permits a fresh intent;
a fresh envelope stages and claims a second full-size SELL:

```text
memory: first=claimed; fresh_owner=True; second=claimed; second_status=submitting
sqlite: first=claimed; fresh_owner=True; second=claimed; second_status=submitting
```

`direct_sell_order_may_execute` returns false when recovery is `needs_review`
(`app/store/core.py:1001-1005`), while each direct-recovery scan includes only
`RECOVERY_UNRESOLVED` (`app/store/memory.py:2485-2519`; `app/store/sqlite.py:3728-3760`). Thus the
dispatch and claim rails see no venue exposure. `tests/test_phase7_sell_intents.py:500-542` pins
fresh-intent eligibility only; `tests/test_wo0036_r2_hostile_closure.py:2086-2126` creates the fresh
owner/envelope beside this exposure but stops before a valid submit.

**Wrong outcome.** If `O1` sold 40 shares that are not yet represented by canonical FILL events,
the store still sizes `O2` from 100 and may sell 140 in total. Ambiguous broker truth therefore
drives a new submission on a human-gated surface. Only FILL events may change quantity, but lack of
a fill event is not proof that the venue did not fill (`CLAUDE.md:34-48`).

**False documentation/evidence claims.**

- ADR-010 says widened retention drives “every sell-side choke” and that the whole sell side
  quarantines (`docs/adr/ADR-010-execution-envelope.md:105-125`).
- INV-090 repeats stage/claim and complete-quarantine claims
  (`docs/INVARIANTS.md:790-825`).
- `BLOCKED-DECISIONS.md:9-16,36-40` calls the current posture a complete, acceptable quarantine.
- Plan §6 OBS-2 says direct exposure remains blocked through `RECOVERY_OPEN_STATUSES`; the code
  shown above selects only `RECOVERY_UNRESOLVED`.

**What resolves it.** Stage and final claim rails must fail closed on same-lineage
`needs_review_child_order_ids`; direct `needs_review` must remain symbol-visible venue exposure at
dispatch and claim even if a fresh intent is allowed to exist. Add both-store pins for recovery
present before stage and appearing between stage and claim. Do not describe accepted
acknowledgement as a preventive choke: the adapter call occurs first
(`app/reconciliation.py:692-755`), so a recovery discovered after the claim cannot retroactively
prevent that already-committed venue request. Such a late discovery must record both exposures
truthfully and quarantine all later activity; it must never be hidden as proof that only one SELL
exists. If X-003 is instead intended to authorize a new claim beside already-known untracked fills,
that requires a new explicit human ratification and corresponding ADR/invariant rewrite.

### P0-4 — The new hold-vs-resurrect test cannot fail when the protected restore keying is broken

`test_needs_review_retention_never_resurrects_an_expired_owner`
(`tests/test_wo0036_r2_close_and_recovery_ownership.py:449-487`) raw-expires the owner, performs a
`BREACHED -> BREACHED` no-op, catches every exception, and asserts the untouched raw value.

A BREACHED same-status transition does not reconcile an owner. Both implementations reconcile a
same-status no-op only when the target is `APPROVED` or `ACTIVE`
(`app/store/memory.py:1573-1601`; `app/store/sqlite.py:2623-2652`). A temporary mutation probe
replaced the reconcile path with one that would wrongly approve the owner if invoked; the test
schedule produced this in both stores:

```text
memory: reconcile_calls=0; owner=expired
sqlite: reconcile_calls=0; owner=expired
```

The implementation's current strict-vs-widened keying appears correct
(`app/store/memory.py:1323-1350`; `app/store/sqlite.py:2351-2379`), but this named safety pin cannot
detect a regression. Repository review rules classify a test that cannot fail as P0.

**What resolves it.** Drive a guaranteed reconcile-bearing public operation—`initialize()` is one
in both stores (`app/store/memory.py:202-217`; `app/store/sqlite.py:476` and its R2 convergence
block)—remove the blanket exception catch, assert no `envelope_delegation_restored` event, and
prove with a targeted mutation that widened-key restore makes the test red.

### P0-5 — The packet's CI-form green claim is not reproducible from the pinned clean checkout

The exact clean target contains 995 tracked files. The default suite did pass once, but the CI-form
command from `.github/workflows/ci.yml:71-74` repeatedly fails at
`tests/test_cockpit_candidates.py:78`:

```text
pytest --cov=app --cov-branch --cov-report=term-missing
1 failed, 3051 passed, 11 skipped, 1 xfailed
coverage: 93.78% (required 93% — coverage gate itself passed)
failure: AppTest script run timed out after 3(s)
```

The same clean default-suite test timed out on one run and passed on the next. More decisively, the
single test passes without coverage in 4.6 seconds but times out under coverage at Streamlit's
hard-coded 3-second `AppTest.run()` default. Neither the test nor `cockpit/app.py`, `pyproject.toml`,
or the CI workflow changed in `5d10c70..f82d953`, so this is baseline debt rather than an R2
semantic regression. It still makes the packet's “every one green” completion claim
non-reproducible, which the repository review rules classify as P0.

**What resolves it.** Give this AppTest an explicit non-flaky timeout/budget that remains sensitive
to a real hang, then rerun the exact CI-form command from a clean checkout. Do not remove the test
or coverage gate.

### P1-1 — Monitoring derives a narrower lineage than the shared store projector

`_validated_envelope_lineage` seeds actions only from exact `event.envelope_id` matches, then adds
duplicates of those same order IDs (`app/monitoring.py:492-552`). The store projections
deliberately discover hostile/malformed actions through every immutable identity: parent envelope,
owner correlation, referenced-order owner, and symbol (`app/store/memory.py:1021-1172`;
`app/store/sqlite.py:1920-2085`).

**Concrete scenario.** Expired envelope `E` owns intent `I`; a live child action has a missing or
wrong parent but `correlation_id=I`, or its order has `sell_intent_id=I`. Store gates see the
malformed obligation and quarantine the symbol. Monitoring loads no action for `E`, projects a
clean empty lineage, emits no R6 malformed-lineage warning, and cannot converge cancellation.
Guessing a cancel target would be unsafe, but losing the diagnostic is also unsafe.

This falsifies INV-090's assertion that no monitoring path derives a neighboring definition
(`docs/INVARIANTS.md:790-816`). Monitoring should load the same bounded identity universe, feed it
to the shared projector, warn on ambiguity, and cancel nothing unless identity is validated. Pin
correlation-keyed and order-owner-keyed hostile cases across both stores and restart.

### P1-2 — The dedicated close-stream parity test is too lossy to pin event truth

`test_close_with_sweep_emits_identical_streams_on_both_stores`
(`tests/test_wo0036_r2_close_and_recovery_ownership.py:295-357`) compares audit events only as
`(event_type, symbol)` and execution events only as
`(event_type, symbol, normalized_dedupe_key)`. It discards payload transitions, reason, actor,
session/correlation relationships, envelope/order identity, source/authority, quantity, and price.

**Concrete failing mutant.** If SQLite attached the sweep event to the wrong owner/session or
emitted an incorrect `spared_sell_intents` payload while preserving event type, symbol, and key
shape, this test would remain green. I found no current source divergence, but the test cannot
support ADR-010's full stream-parity claim or the human-gated event-truth guarantee.

Compare canonicalized full model dumps, consistently map generated entity IDs, exclude only
ingest timestamps/random IDs, and include retry/restart plus rollback injection.

### P1-3 — Structural performance is sound, but accepted wall-clock gates remain red and stress startup is convex

Every target/baseline/stress run kept the structural criteria green: 15 SELECTs at both normal
scales, query count independent of corpus size, no unrelated full scans, and about 310 KB projection
peak memory. The official target gate nevertheless exited 1 on every run. Observed target ratios
were approximately `3.39-6.14x` runtime against a `3x` budget and `14.49-15.89x` startup against a
`12x` budget. The unchanged baseline gate also exited 1 and was noisy (`2.34-7.21x` runtime,
`16.13-16.81x` startup), establishing that the wall-clock miss predates R2.

Stress kept structural gates green but quantified a material convex Python-side startup cost:
realistic startup was `1.59-1.81s`; the 1,000-symbol/100,002-event corpus took `120.70-130.69s`
(`72.29-75.87x`). The Claude-ported gate also exited 1 (`3.95x` runtime, `16.96x` startup).

Performance alone would support **ACCEPT-WITH-CHANGES with a dedicated performance work order**,
not an immediate re-budget: the indexed structure works and the default miss is baseline-proven,
but the stress curve is real enough to measure and optimize before beta-scale reliance. It is not
the reason for this BLOCK verdict.

## Seven-lens closure record

1. **Treadmill sibling classes.** Masked predecessors are found by the shared, bounded projector at
   all five choke points; release-while-child-rests, orphan-at-close, double-mandate, and ordinary
   blind-resubmit/blind-cancel classes are closed by source and both-store pins. Stale-read flatten
   is closed only for the declared three-status set; P0-1 falsifies closure over the nonterminal BUY
   property. P0-2 falsifies cross-side closure across the Candidate-to-Order handoff and both direct
   exit mint paths. P0-3 falsifies the needs-review second-SELL property.
2. **Three retention predicates.** `strict` correctly drives promote/restore/conflict sweep;
   `widened` correctly prevents release but is not consumed by every submission choke (P0-3);
   `across-close` correctly excludes only bare pre-activation approval. Hold-vs-resurrect source
   keying is sound, but its claimed pin is inert (P0-4).
3. **Session-close truth.** I found no implementation defect in the P-A sweep. Both stores collect
   the same envelope/action/order/recovery facts; memory closes within `_atomic`
   (`app/store/memory.py:4300-4438`), SQLite in one transaction
   (`app/store/sqlite.py:6091-6197`), both sweep before owner expiry with one close timestamp, and
   both snapshot positions from FILL-event truth. Full-fidelity parity remains under-tested (P1-2).
4. **Option B flatten.** Continuous-lock TOCTOU closure and override preservation are green for the
   detected set. Retry convergence is false by lifecycle property (P0-1), and the broader
   self-cross property remains open across approved/fresh BUY dispatch after the mint (P0-2).
5. **Oracle legitimacy.** Green. `15c2dd6..f82d953` changes the Codex oracle by exactly 10 additions
   and 0 deletions, all in `_seed_long`: explanatory setup plus
   `transition_order(..., CANCELED)`. All 53 assertion lines are byte-identical. The final oracle
   overlaid on both `15c2dd6` and `fa4437d` produces the same four P-A/P-B failures; target code
   makes all 61 pass. D1 is a setup-only reseed, not oracle weakening.
6. **Docs vs code.** INV-037/052 and the close portions of ADR-010/INV-081 agree with the source.
   ADR-010/INV-081 overstate Option B convergence (P0-1); the runtime flatten/protection comments
   overstate cross-side closure beyond the detected Order set (P0-2); ADR-010/INV-090 overstate
   widened sell-side quarantine (P0-3); INV-090 overstates monitoring keying (P1-1).
7. **Named P4 performance finding.** Structural acceptance is justified; silent green status or
   re-budgeting is not. Record and execute a performance work order (P1-3).

## PD-1 assessment

Parking the needs-review reconciliation API was procedurally correct: it is a new human-gated
event-truth surface and needs explicit authorization. The stated premise that the current system is
already a complete fail-closed quarantine is unsound because P0-3 proves two submission lanes.

The sketch is directionally right but incomplete. A status flip must never itself overwrite
position or serve as a synthetic fill. The future design should require broker-terminal evidence,
immutable execution IDs, cumulative-fill parity, identity validation across recovery/order/action/
envelope/owner, actor/reason/evidence, retry idempotency, and atomic revalidation. Every discovered
fill must enter canonical position truth as a deduplicated FILL event. Clearing one recovery may
remove only that recovery's contribution; it cannot promise the whole quarantine lifts while any
other strict, malformed, recovery, or venue obligation remains.

The sketch's phrase “broker/human-authoritative” must also be split into honest provenance. The
current `EventSource` vocabulary has no human source and `EventAuthority` has only
`BROKER_AUTHORITATIVE`, `LOCAL`, and `SYNTHETIC` (`app/models.py:466-491`). A human attestation must
never be mislabeled broker-authoritative. The follow-up design needs an explicit human-attested
source/authority (or an audit-to-execution bridge with equivalent semantics), while actual broker
executions retain immutable broker provenance and enter position truth only through canonical,
deduplicated FILL events.

## Human-gate and scope audit

The diff touches order submission/claim, cancel/manual-flatten behavior, event-log truth, and tests/
ADRs. Those surfaces are human-gated by `CLAUDE.md:48-60`. I found an explicit authorization chain
for the intended work: the Part A decisions, Ameen's Part B D1-D9 ratification plus the four
recorded defaults, and the executed completion plan. No live-trading enablement was introduced in
the reviewed diff. No table/data-shape migration was introduced; the two
additive, idempotent SQLite startup indexes at `app/store/sqlite.py:530-547` were covered by the
recorded D9 pre-approval. The defects above are implementation/test-claim failures inside that
authorized scope, not evidence that the builder silently expanded the approved scope.

## Verification evidence

All commands were run against a clean archive containing exactly the tracked files at the pinned
SHA. The shared checkout itself contains pre-existing untracked `.agents/` and `.codex/` trees;
literal `ruff check .` sees those unrelated plugin files, while the pinned clean archive passes.

| Verification | Fresh result |
|---|---|
| `ruff check .` | PASS |
| `ruff format --check .` | PASS — 240 files formatted |
| `mypy app/` | PASS — 64 source files |
| `lint-imports` | PASS — 6 contracts kept |
| `pytest -q` | PASS on clean rerun, 245.2s; an earlier run hit P0-5 |
| `pytest -q tests/r2_conformance_oracle.py` | PASS — 61 cases; explicitly invoked |
| `pytest -q tests/test_r2_conformance_oracle_claude.py` | PASS — 22 passed, 6 recorded skips |
| `pytest --cov=app --cov-branch --cov-report=term-missing` | FAIL — P0-5; coverage itself 93.78% |
| `python -m tests.performance.r2_scaling_gate` | FAIL as packet predicts; structural gates green, P1-3 |

Additional independent public-API/engine probes reproduced P0-1; P0-2 across manual flatten,
autonomous protection, both claim orders, and the ordinary submission sweep; and both P0-3 variants
in memory and SQLite. A mutation/spy probe established P0-4's reconcile path was called zero times.
A canonicalized full-stream recheck also found the current close outputs equal across stores (25
audit and 10 execution events), so P1-2 remains a pin-strength defect rather than a found source
divergence. Oracle provenance was checked at both baselines, and performance was repeated at target,
parent baseline, and stress scale.

## Could not verify

- No live Alpaca call or live/shadow mode was exercised; review remained Paper/local only.
- The packet states the turnkey commands were green at `f083222`, while the operator pinned this
  review to the later `f82d953`; all verdict evidence above is for the requested pinned SHA.
