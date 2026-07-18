# REV-0029 — Independent Correctness Review, Round 2

**Reviewer:** Codex (independent review seat)

**Review date:** 2026-07-17 HST / 2026-07-18 UTC

**Pinned branch/SHA:** `consolidate/r2-canonical` at
`70b5567966ed33782a5f53048be6f48d2370e597`

**Diff reviewed:** `abfbae9..70b5567`

## Verdict

**BLOCK**

P0-1 and P0-2 remain open through one production-reachable race: the flatten cancel helper can
act on a stale `CREATED` snapshot after the submission sweep has claimed the BUY, locally changing
the current `SUBMITTING` row to `CANCELED`. The flatten and cross-side claim rails then see only the
terminal local row, not the in-flight or recovery-owned broker BUY, and submit the exit SELL. The
schedule was reproduced deterministically in both stores through the production facade and
monitoring submission paths.

P0-3's intended consumers now exist, but the universal quarantine property remains open. The public
recovery write accepts identity fields that contradict its referenced order. An order-id-only
`needs_review` lookup then suppresses the real AAPL SELL from one exposure scan, while the recovery
scan looks under the contradictory declared symbol/side. A second AAPL SELL reaches `SUBMITTING` in
both stores. In addition, the claimed final-claim regression pin and Tier-1 consumer gate stay green
when the actual sibling-claim consumers are deleted.

P1-1 also remains open exactly at the symbol-only boundary named by the round-2 request. P1-2's
rollback variants are real and atomic, but the parity canonicalizer still erases deterministic,
semantic timestamps and therefore closes only the current instance, not the property.

No application, test, ADR, or request file was changed during review. This result file is the only
review-side write.

## Findings

### P0-1 — Flatten can mint and submit beside a locally terminal but venue-live BUY

**Judgment: still-open.** `FLATTEN_BLOCKING_BUY_STATUSES == NON_TERMINAL_ORDER_STATUSES` is enforced,
but nonterminal totality is not equivalent to “this BUY can no longer fill.” A locally terminal
order can have an in-flight broker call or an open `SubmitRecoveryRecord`.

The deterministic schedule is:

1. The first flatten attempt returns `FLATTEN_BUYS_OPEN` for an AAPL BUY that is `CREATED`.
2. `cancel_open_buys` snapshots that row through `list_orders()` at `app/monitoring.py:263` and
   pauses with the snapshot still saying `CREATED`.
3. The normal submission sweep claims the same BUY at `app/monitoring.py:1215-1244`, atomically
   moving the current row to `SUBMITTING`, then awaits the broker adapter at
   `app/monitoring.py:1267-1268`.
4. The cancel helper resumes and selects its branch from the stale object. It calls the generic
   transition to `CANCELED` at `app/monitoring.py:271-274`. `SUBMITTING -> CANCELED` is legal at
   `app/transitions.py:111-121`; there is no expected-current-status comparison.
5. The facade retry at `app/facade/store_backed.py:867-895` sees a terminal local BUY. Flatten scans
   projected order status only (`app/store/memory.py:2790-2796`,
   `app/store/sqlite.py:4053-4061`) and mints the manual SELL.
6. The SELL's final claim also scans only projected BUY order statuses
   (`app/store/memory.py:2588-2610`, `app/store/sqlite.py:3819-3837`). It ignores BUY-side submit
   recoveries, so it claims and submits. If the BUY acknowledgement lands first, persistence fails
   at `app/monitoring.py:1369-1380` and `_handle_unpersisted_submit` creates the recovery at
   `app/monitoring.py:1909-1923`; if the SELL claim wins first, both broker calls are already in
   flight before that recovery exists.

Fresh two-store output, using the real facade, cancel helper, submission sweep, claim methods, and a
deterministically blocked paper adapter:

```text
memory: stale_snapshot=created; buy_after_flatten=canceled;
        recovery=['unresolved']; buy_final=canceled; sell_final=submitted;
        broker_sides=['buy', 'sell']; buy_venue_live=True; sell_venue_live=True
sqlite: stale_snapshot=created; buy_after_flatten=canceled;
        recovery=['unresolved']; buy_final=canceled; sell_final=submitted;
        broker_sides=['buy', 'sell']; buy_venue_live=True; sell_venue_live=True
```

The recovery is not speculative metadata. `SubmitRecoveryRecord` explicitly denotes an order that
is live at the broker while the local row is `CANCELED` or `REJECTED`
(`app/models.py:884-912`).

Fresh enumeration over every `OrderStatus`:

| Status | Can a later fill still be recorded? | Current flatten treatment |
|---|---|---|
| `CREATED` | Yes, after claim; the counterexample begins here. | Blocking, but the stale helper can terminalize the already-claimed row. |
| `SUBMITTING` | Yes; broker acceptance is in flight/uncertain. | Blocking until the stale `CREATED` branch changes it to `CANCELED`. |
| `SUBMITTED` | Yes. | Blocking; ordinary cancel moves it to still-blocking `CANCEL_PENDING`. |
| `PARTIALLY_FILLED` | Yes, up to remaining quantity. | Blocking; ordinary cancel moves it to still-blocking `CANCEL_PENDING`. |
| `CANCEL_PENDING` | Yes; late-fill reconciliation is intentional. | Blocking and not blindly recancelled. |
| `TIMEOUT_QUARANTINE` | Yes/ambiguous by definition. | Blocking and not blindly cancelled. |
| `FILLED` | No additional valid quantity; the cumulative order bound rejects an extra nonduplicate fill, and its fills are already in position truth. | Nonblocking. |
| `CANCELED` | Yes when local terminalization raced an accepted submit; the recovery model explicitly owns this case. | Nonblocking, including while an open BUY recovery exists. |
| `REJECTED` | The same recovery model permits a locally rejected row whose upstream acceptance was not persisted. | Nonblocking, including while an open BUY recovery exists. |

The enum sets themselves are total: the fresh enumeration produced
`FLATTEN_BLOCKING == NON_TERMINAL == {created, submitting, submitted, partially_filled,
cancel_pending, timeout_quarantine}` and `MAY_EXECUTE == NON_TERMINAL - {created}`. Removing
`CANCEL_PENDING` from the flatten set turns `tests/test_review_hardening_gates.py:46-61` red.
The gate therefore enforces the stated equality; the equality is the wrong complete property because
it omits terminal-local/open-recovery execution exposure.

**Why it matters.** The SELL can liquidate the fill-derived position while the BUY is still accepted
or fillable, allowing both sides to rest or the BUY to regrow the position being flattened.

**What resolves it.** Make local cancellation conditional on the row still being `CREATED` in the
same store lock/transaction; a stale snapshot must not terminalize a claimed `SUBMITTING` order.
Define same-symbol BUY execution exposure over projected Order state **and** open
`SubmitRecoveryRecord` state (`unresolved` and `needs_review`), and consume that projection in both
flatten and final exit-SELL claim. Pin the exact dual-store schedule above.

### P0-2 — The Candidate/Order claim rail is sound for ordinary rows but not for BUY recoveries

**Judgment: still-open.** The `CREATED` asymmetry is safe under the ordinary order-state model, but
P0-1 creates a broker-live BUY that the model represents as terminal-local plus recovery. That BUY
is outside `MAY_EXECUTE_ORDER_STATUSES`, so either manual flatten or autonomous protection can pass
the same final exit claim.

The full ordinary ordering matrix was probed in both stores:

| Ordering/path | Layer that closes it at HEAD |
|---|---|
| Manual exit opens while Candidate is `PENDING`/`APPROVED`, including the approval→dispatch await gap | Atomic candidate stand-down at `app/store/memory.py:2630-2663,2888` / `app/store/sqlite.py:3854-3887,4149`; resumed dispatch refuses at `memory.py:3049-3074` / `sqlite.py:4354-4378`. |
| Autonomous protection opens in that gap | The same stand-down at `memory.py:2430` / `sqlite.py:3671`, followed by dispatch refusal. |
| Candidate dispatch creates BUY first, then manual flatten | Flatten detects the `CREATED` BUY and returns `FLATTEN_BUYS_OPEN`; no SELL is minted. |
| Candidate dispatch creates BUY first, then protection opens | Protection may create a SELL, but the final claims serialize under the store lock. |
| Both Orders are `CREATED`; BUY claim runs first | BUY becomes `SUBMITTING`; SELL claim sees a BUY in `MAY_EXECUTE` and blocks. |
| Both Orders are `CREATED`; SELL claim runs first | SELL becomes `SUBMITTING`; BUY claim sees the nonterminal exit and blocks. |
| Concurrent claims | The check and `CREATED -> SUBMITTING` write share one lock/transaction (`memory.py:3280-3412`; `sqlite.py:4593-4737`), reducing to one of the prior two orderings. |
| Kill/quarantine gate precedes cross-side reason | It returns `blocked` without a claim write; after the control clears, retry reaches the cross-side gate. It never falls through as `claimed`. |

Fresh outputs included: exit-first expired the Candidate with zero BUY orders; dispatch-first/manual
returned `buys_open`; both claim orderings produced exactly one `claimed` side; kill-active returned
`blocked:kill_switch`, then `blocked:same-symbol exit may execute` after release.

The counterexample falls outside every row in that otherwise-complete matrix. After the stale local
cancel, the BUY is `CANCELED` and either (a) its adapter request is still in flight, or (b) its open
recovery records the accepted broker order. The SELL predicate at `memory.py:2588-2610` and
`sqlite.py:3819-3837` reads only `Order.status`; the only recovery-aware same-symbol helpers are
SELL-side (`memory.py:2506-2523`; `sqlite.py:3746-3760`). Both the manual and protection SELLs use
the same final claim, so both can pass beside this BUY exposure.

**What resolves it.** The P0-1 correction closes the escape: make stale local cancel impossible and
include open BUY recovery truth in the symmetric final claim. Retain the current candidate
stand-down, dispatch refusal, ordinary order predicates, and claim atomicity.

### P0-3 — A scope-inconsistent `needs_review` recovery de-indexes the actual SELL exposure

**Judgment: still-open.** For a correctly scoped recovery, all four intended lanes are implemented
in both stores:

| Recovery timing / owner | Memory rail | SQLite rail | Fresh result |
|---|---|---|---|
| Same envelope, before stage | `app/store/memory.py:1941-1947` | `app/store/sqlite.py:3084-3090` | Stage refused. |
| Same envelope, between stage and claim | `memory.py:3191-3197` | `sqlite.py:4529-4535` | Corrected prior-sibling schedule blocked with explicit `needs_review` reason. |
| Direct/fresh owner, before mint or stage | `memory.py:2471-2559` plus its create/stage callers | `sqlite.py:3713-3785` plus its callers | Fresh owner/action refused. |
| Direct/fresh owner, between mint/stage and claim | `memory.py:3239-3241` | `sqlite.py:4585-4587` | Final claim refused. |

Fresh grep also confirms a real producer and real consumers:

```text
app/store/core.py:1080,1464-1484,1581       projection field + producer
app/store/memory.py:1941-1947,3191-3197     stage + final claim
app/store/sqlite.py:3084-3090,4529-4535     stage + final claim
```

The universal property nevertheless fails at the recovery ingress. Both stores accept a recovery
without comparing its immutable scope to the existing `local_order_id`
(`app/store/memory.py:3417-3448`; `app/store/sqlite.py:4791-4822`). The following uses only public
store calls:

1. Hold 100 AAPL shares through a real BUY fill.
2. Create/approve direct AAPL SELL intent `I1`; create and claim `O1`; mark it `SUBMITTED`, then
   `CANCELED`.
3. Create `RECOVERY_NEEDS_REVIEW` for `local_order_id=O1.id` but declare `symbol='MSFT'`, `side=SELL`.
4. Create/approve fresh AAPL intent `I2`, mint `O2`, and claim it.

Observed in memory and SQLite:

```text
I2 != I1
O2.sell_intent_id == I2.id
second_claim == claimed
O2.status == submitting
```

Declaring `symbol='AAPL', side=BUY` instead produces the same result. The order-id-only
`needs_review` set makes `direct_sell_order_may_execute` return false for O1
(`app/store/core.py:1019-1025`; memory use at `app/store/memory.py:2477-2503`; SQLite use at
`app/store/sqlite.py:3726-3743`). The recovery scan then reconstructs exposure only under the
record's declared symbol/side (`memory.py:2517-2523`; `sqlite.py:3749-3760`). The AAPL SELL therefore
disappears from both paths.

All five current application producers copy symbol, side, quantity, price, and session from the
same Order (`app/monitoring.py:755-768,1758-1772,1913-1923,2351-2366` and
`app/reconciliation.py:542-558`), so the normal current call graph cannot originate the mismatch.
That does not close the stated property: `create_submit_recovery` is the store's persisted-fact
ingress, it accepts the contradictory fact, and the repository explicitly tests malformed internal
state to require fail-closed behavior.

**Why it matters.** A `needs_review` record denotes unresolved broker SELL exposure. A contradictory
scope must not silently remove the referenced order from its actual symbol's quarantine and
authorize a second SELL.

**What resolves it.** At recovery creation, validate immutable recovery scope against an existing
local order in the same lock/transaction. For legacy/malformed persisted mismatches, quarantine the
referenced order's scope as well as the record's declared scope (or reject startup/action with a
diagnostic); never let one identity suppress the other.

### NEW-P0-1 — The final-claim pin cannot fail when its intended sibling consumer is deleted

**New mechanical finding.** `tests/test_wo0108_rev0029_remediation.py:268-319` says it creates a
prior sibling exposure, but lines 300-315 create the recovery on `staged2.order.id` and then claim
that same order. It therefore trips the current-order recovery guard at
`app/store/memory.py:3128-3133` / `app/store/sqlite.py:4455-4461` before reaching the intended
prior-sibling consumers at `memory.py:3191-3197` / `sqlite.py:4529-4535`.

Mutation evidence:

```text
delete memory.py:3194-3196 and sqlite.py:4532-4535
named final-claim test: 2 passed
Tier-1 hardening gate: passed

corrected schedule (O1 staged/canceled; O2 staged; needs_review latched on O1; claim O2):
HEAD memory/sqlite: blocked, explicit needs_review reason
mutated memory/sqlite: claimed -> SUBMITTING
```

Deleting both final direct-exposure claim checks likewise leaves all six named P0-3 lane tests green,
while an order staged before a direct O1 becomes `needs_review` claims successfully under the
mutant. This meets the repository's P0 rule for a human-gated test that cannot fail when the guarded
branch is removed.

**What resolves it.** Correct the test fixture so recovery belongs to a distinct prior sibling, and
add the fresh-owner stage-before-latch/final-claim schedule. Mutation-check each stage and claim
consumer independently in both stores.

### P1-1 — Symbol-only malformed lineage is still invisible to monitoring

**Judgment: still-open.** The owner-keyed additions work, but the deliberately excluded symbol key
creates exactly the blind spot posed in the request.

Fresh hostile persisted-state probe:

```text
expired envelope E: owner=I, symbol=AAPL
live child O: SUBMITTED AAPL SELL, sell_intent_id=J
ENVELOPE_ACTION: envelope_id=missing-E, correlation_id=K, order_id=O
I, J, and K are distinct; only the action/order symbol relates the row to E
```

Both stores produced:

```text
symbol projection: invalid_order_ids=[O], missing_envelope_ids=[missing-E]
new AAPL intent through the store gate: refused
monitor projection for E: actions=0, clean-empty
R6 warnings=0; broker cancel attempts=0; O.status=submitted
```

Store symbol selection admits either event or referenced-order symbol at
`app/store/memory.py:1103-1106` and `app/store/sqlite.py:2015-2017`. Monitoring admits parent,
correlation, referenced-order owner, or co-order identity at `app/monitoring.py:538-556` and
explicitly excludes the symbol at `app/monitoring.py:510-523`. The R6 warning is downstream of that
selection at `app/monitoring.py:676-716`, so it cannot diagnose the omitted action.

The correlation pin is also not exclusive: `_seed_owner_keyed_hostile_lineage` always assigns the
child's owner to E's owner at `tests/test_wo0036_r2_hostile_closure.py:3629-3643`, including the
`key='correlation'` case. Deleting the correlation branch at `app/monitoring.py:541-542` leaves the
two correlation-labelled tests green because referenced-order ownership still selects the action.
An exclusive-correlation fresh fixture does exercise the implementation and warns in both stores;
the implementation branch works, but its named pin is instance-only.

**Why it matters.** Store gates quarantine the symbol, yet cancel convergence reports no malformed
lineage diagnostic and leaves the live child untouched. The claimed INV-090 correction—never
clean-and-empty for work the store quarantines—is false.

**What resolves it.** Give monitoring a symbol-scoped diagnostic convergence matching the store's
symbol selector, while continuing to refuse a broker cancel unless owner/order identity validates.
Make the correlation and referenced-order-owner tests mutually exclusive by construction.

### P1-2 — Close is atomic, but parity remains over-canonicalized

**Judgment: instance-only.** No current non-time/non-ID store divergence was found: fresh raw dumps
contained 25 audit and 10 execution events per store; after accounting for generated IDs and clocks,
every stable field matched. Restart and retry variants also pass.

The rollback proof is genuine. The injected second audit-write failure at
`tests/test_wo0036_r2_close_and_recovery_ownership.py:452-505` was instrumented independently. Before
the throw, both stores had staged one audit event, one execution event, one envelope expiry, and one
candidate expiry. After the throw, every memory atomic-snapshot collection and every SQLite table
matched its pre-close state; session remained `ACTIVE` and owner `APPROVED`. The implementation's
single units are `app/store/memory.py:4498-4501` and `app/store/sqlite.py:6273-6379`.

The parity comparator is still not a property check. `_canon_streams` replaces every datetime object
and every ISO-looking substring anywhere in a model dump at
`tests/test_wo0036_r2_close_and_recovery_ownership.py:310-327`. That erases semantic
`ExecutionEvent.ts_event` and deterministic payload values such as `expires_at`, not merely ingest
clock noise.

Fresh mutation:

```text
payload.expires_at: 2026-07-15T20:00:00+00:00 -> 2031-01-02T03:04:05+00:00
raw comparator detects divergence:       true
current canonical comparator detects it: false
```

**What resolves it.** Normalize only explicitly nondeterministic identity and ingest-clock fields.
Preserve causal/event times and deterministic timestamp-bearing payload fields, or inject common
ID/clock sources into the two-store script and compare full raw dumps.

### NEW-P1-1 — Tier-1 T1.3 gates count filenames, not producers or rail consumers

**New finding.** `tests/test_review_hardening_gates.py:85-116` returns only basenames containing a
raw substring. It cannot distinguish a field declaration, import, comment, producer assignment,
stage consumer, or final-claim consumer.

Fresh regression injections:

| Mutation | T1.3 result | Behavioral result |
|---|---|---|
| Remove only `needs_review_child_order_ids=tuple(needs_review_children)` at `app/store/core.py:1581`; leave the field declaration. | Green | Same-envelope stage property fails in both stores. |
| Remove memory stage consumer at `app/store/memory.py:1941-1947`. | Green | Memory behavior fails. |
| Remove SQLite stage consumer at `app/store/sqlite.py:3084-3090`. | Green | SQLite behavior fails. |
| Remove only final sibling claim consumers at `memory.py:3194-3196` / `sqlite.py:4532-4535`. | Green | Corrected sibling claim reaches `SUBMITTING` under each mutant. |
| Replace the real memory `MAY_EXECUTE_ORDER_STATUSES` expression at `app/store/memory.py:2608` with an empty set, leaving import/comment mentions. | Green | Exit SELL claims beside a `SUBMITTED` BUY. |
| Same at `app/store/sqlite.py:3835`. | Green | Same behavioral failure. |

The T1.1 enum gates are effective: removing `CANCEL_PENDING` independently from the nonterminal,
flatten-blocking, or may-execute sets turns the relevant assertion red at lines 43, 52, and 70.
T1.3 turns red only after every mention is removed from a required basename, which is not the
claimed producer/consumer guarantee.

**What resolves it.** Replace basename substring tests with an explicit producer/consumer table
keyed to independently mutation-checked behavior, or an AST-based check that identifies assignment
and executable use sites. The required stage and final-claim consumers must be distinct entries for
each store.

### NEW-P1-2 — The review diff reintroduces 403 out-of-scope tooling files

**New finding.** Fresh diff and tracked-file enumeration show `abfbae9..HEAD` adds 368 files under
`.agents/` and 35 under `.codex/`—403 tracked files and 91,527 added lines. These paths are absent
from WO-0108's `allowed_paths` at `work/active/WO-0108-rev0029-remediation.md:26-46`.

This contradicts the disposition's statement that the contamination was dropped
(`work/review/REV-0029/disposition.md:10-16`) and the round-2 request's statement that the clean
archive sees only tracked source (`request-round2.md:42-43`). `.gitignore:47-51` prevents new
untracked additions; it does not untrack files already introduced through the merge ancestry.

**Why it matters.** This is 91k lines of scope creep in a high-risk, path-bounded remediation diff,
and it makes the packet's branch-hygiene claim false. No paper-order behavior change was found in
these tooling files.

**What resolves it.** Remove the 403 tracked tooling files from this branch through a normal scoped
commit, retain the ignore entries, and re-run the literal clean-checkout gates.

## Per-finding closure disposition

| Round-1 finding | Round-2 judgment | Closure basis |
|---|---|---|
| P0-1 flatten/late-fill | **still-open** | Production stale-snapshot race plus ignored BUY recovery; reproduced in both stores. |
| P0-2 same-symbol self-cross | **still-open** | Ordinary candidate/order matrix is closed, but the same terminal-local/open-recovery BUY bypasses final claim. |
| P0-3 `needs_review` quarantine | **still-open** | Honest, correctly scoped lanes are implemented; scope-inconsistent public recovery ingress permits a second SELL in both stores. |
| P0-4 inert hold-vs-resurrect test | **closed-by-property** | `initialize()` reaches owner reconciliation; isolated `retains_intent_strict -> retains_intent` mutation fails the named test in both stores at line 634 (`APPROVED` vs `EXPIRED`). |
| P0-5 coverage/AppTest timeout | **closed-by-property** | Fresh grep found exactly five constructors, all `default_timeout=30`; all 31 cockpit tests passed under coverage, and the original case took 7.70s under coverage—above the former 3s and below 30s. |
| P1-1 monitoring lineage | **still-open** | Symbol-only store-quarantined action projects clean-empty in monitoring, with no warning/cancel, in both stores. |
| P1-2 close parity/variants | **instance-only** | Current streams match and rollback is truly atomic, but a semantic `expires_at` mutation is erased by canonicalization. |
| P1-3 performance | **still-open / previously deferred** | Fresh `python -m tests.performance.r2_scaling_gate` remains red: runtime p95 ratio `4.0178 > 3`; startup elapsed ratio `20.3711 > 12`; structural scan/query/heap gates pass. This was not claimed remediated by WO-0108. |

## Required fresh INV/ADR probes

- **INV-090 — FAIL:** A symbol-only AAPL hostile action with missing parent, stranger correlation,
  and stranger order owner is malformed in both stores' symbol projection but clean-empty in
  `_validated_envelope_lineage`; zero R6 warnings/cancels and child remains `SUBMITTED`.
- **INV-081 — FAIL:** While a manual flatten is cancelling a snapshotted `CREATED` BUY, the normal
  sweep claims it. The stale branch changes current `SUBMITTING -> CANCELED`; flatten then mints and
  submits its SELL while the BUY is live/in recovery, in both stores.
- **ADR-010 §3 — PASS for a fresh honest sibling, FAIL for malformed scope:** Stage O1 then cancel it,
  stage O2, latch `needs_review` on O1, claim O2: HEAD blocks with the explicit sibling rail in both
  stores. Declare O1's recovery under a contradictory symbol/side through the public ingress, and a
  fresh AAPL O2 claims to `SUBMITTING` in both stores.
- **ADR-010 §4 — FAIL:** The same production flatten/submission interleaving violates the amended
  “BUY and exit SELL can never both reach the venue” correction; both paper adapter sides remain live.

## Verification evidence

| Command/probe | Result at pinned SHA |
|---|---|
| `ruff check . && ruff format --check . && mypy app/ && lint-imports` | PASS; 484 files formatted, 64 app files type-checked, 6 import contracts kept. |
| `pytest -q` | PASS, exit 0 in 493.4s; expected skips/xfail only. |
| `pytest -q tests/r2_conformance_oracle.py` | PASS, 61 tests. |
| `pytest -q tests/test_r2_conformance_oracle_claude.py` | PASS, 22 passed / 6 documented skips. |
| `pytest -q tests/test_review_hardening_gates.py` | PASS, 5 tests; mutation limitations reported above. |
| Corrected P0-3 sibling mutation | HEAD blocks both stores; deleting the final sibling consumer claims in the corresponding store while named pin/gate stay green. |
| P0-4 intended mutation | Named test fails in both stores. |
| Five AppTest sites under coverage | 31 passed in 81.12s; original case 1 passed in 7.70s with `--cov-fail-under=0`. |
| `python -m tests.performance.r2_scaling_gate` | FAIL on the two known wall-clock ratios; structural gates pass. |

**Could not verify:** no paper broker sandbox call was needed or made; all counterexamples use the
repository's paper/mock adapter and both local stores. The untracked-file claim was verified from the
actual Git index and diff, not from a reconstructed archive. No clean-clone run was necessary to
establish the reproduced state-machine failures.
