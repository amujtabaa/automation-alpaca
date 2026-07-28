---
type: Review Result
rev_id: REV-0044
title: "WO-0104a R6a — rails store surface: durable rail state, projector, epoch identity, atomic budget + rate debits, release primitive"
reviewer_seat: Claude (independent review seat; implementer was Codex)
implementer_branch: codex/signal-r6a-rails-store
head_sha: b48235e
base_sha: 6955208
verdict: ACCEPT-WITH-CHANGES
p0_count: 0
p1_count: 2
gating_items: [R-1, R-2]
named_review_item: "Stop 2 payload conformance — DISCHARGED, exact match"
reviewed: 2026-07-27
---

# REV-0044 — WO-0104a R6a, verdict **ACCEPT-WITH-CHANGES**

Independent review of `codex/signal-r6a-rails-store` at `b48235e`, based on `origin/master` `6955208`.
Method: four parallel passes — three adversarial lenses in isolated worktrees plus the review seat's own
verification — followed by planning-seat reproduction of every P1 before it entered this record.

**No P0.** Every decisive pin the work order mandated is **live, not inert**, verified by independent
mutation rather than by reading the implementer's transcript. The delivered logic is correct on all four
surfaces the work order gated. **Two P1s gate the packet**, and they share one root cause.

The implementer's own internal audit returned ACCEPT. Per CLAUDE.md that is in-process validation and
carries no weight here; it is recorded only because the request correctly disclosed it and correctly
stated that it "does not substitute for REV-0044".

## The named review item — DISCHARGED

The operator's 2026-07-26 ratification satisfied only the operator half of
`SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md:110-113`. This packet owes the other half, and discharges it:

**The emitted `PRODUCER_QUARANTINED` payload EXACTLY matches the ratified field list** — on both breach
paths, on both stores. No extra field, no missing field, no unratified vocabulary value. `epoch_start` is
carried as an ISO string, so `normalize_json_payload` never sees a raw `datetime`. Measured emission:

```
memory / budget: {"breach_trigger":"budget_exhausted","cycle_budget_consumed":2,"cycle_budget_limit":2,
                  "epoch_sequence":1,"epoch_start":"2026-07-26T12:00:01+00:00","producer_id":"producer-a"}
memory / rate:   {"breach_trigger":"rate_breach","bucket_capacity":2,"epoch_sequence":1,
                  "epoch_start":"2026-07-26T12:00:02+00:00","producer_id":"producer-r"}
sqlite: identical on both paths.        EXTRA=[]  MISSING=[]
```

Conformance is **ratcheted, not merely observed**: `_require_exact_payload_fields`
(`app/events/projectors.py:1076-1084`) fails the fold closed on drift. Injecting `"detected_by": "rails"`
turns three tests RED. Both D-R6a-17 epoch shapes are reachable and fold correctly — mid-cycle
(`limit=5 consumed=2 trigger=rate_breach`) and fresh (`limit=None consumed=0`).

**No new gated surface was taken.** The ratified list was implemented exactly; nothing beyond it was
appended.

---

## The root cause behind both P1s

`D-R6a-3` ratified the rail row as a **cache, rebuilt at `initialize()`**. The implementation instead made
the **fold authoritative on live paths** — re-projecting the entire execution-event log on every
attributable rejection, and folding the entire log at startup.

In one respect that is *stronger* than specified: with no increment to get wrong, the double-charge that
war-game pass 3 raised as a P0 becomes **structurally impossible**. The identity discriminator ends up
load-bearing for the **opener**, not the debit. That is a defensible engineering choice and it is why the
correctness surfaces all pass.

But it produces both P1s, and it was never disclosed as a departure from the ratified design. **The
remediation decision is therefore the planning seat's and the operator's, not the implementer's: where is
rail state authoritative, and where is it a cache?** Answer that once and both findings close together.

---

## Findings

Convergence is recorded because it bears on confidence: three lenses ran blind to each other.

| # | Sev | Finding | Found by |
|---|---|---|---|
| **R-1** | **P1** | A pre-R6a event log **bricks `initialize()` for the entire store** — not just the seat | 2 lenses + reviewer repro |
| **R-2** | **P1** | O(global event log) fold per attributable ingest / breach / release, **inside the single-writer lock** | 2 lenses + reviewer repro |
| R-3 | P2 | `release_producer` gates on **different state per store**; memory fail-opens where SQLite fail-closes | **3 lenses** |
| R-4 | P2 | `consumed == limit` with a closed epoch is a **permanent, unreleasable 403 wedge** with no exit | 1 lens |
| R-5 | P2 | Append-only log validated against **mutable** caps; lowering one retroactively bricks startup | 1 lens |
| R-6 | P2 | The ingest gate trusts the cache with **no fold cross-check** on the ordinary path | 1 lens |
| R-7 | P2 | The budget cap is now declared **four** times, two of them new | 1 lens |
| R-8 | P2 | The store→facade prohibition pin is **CWD-dependent** and passes vacuously off-root | 1 lens |
| R-9 | P2 | The `consumed >= limit` half of the gate is **unpinned** | 1 lens |
| R-10 | P3 | `_record_response` branches on `record is None`, not on the outcome | 2 lenses |
| R-11 | P3 | Seven durable columns co-written through `getattr` on `rail: object` — mypy-invisible | 1 lens |
| R-12 | P3 | The R4 property corpus passes `producer_rail=None` on every generated plan | 1 lens |
| R-13 | P3 | `_producer_rail_contract()` re-executes an import **per fold event** | 1 lens |

### R-1 (P1) — a pre-R6a log bricks the whole store

**Reproduced by the review seat**, not relayed. A database generated with the code at `6955208` — the
commit merged to master hours before this branch — cannot be opened by `b48235e`:

```
initialize() RAISED ProjectionError:
  signal_quarantined event sequence=51 exceeds the projected cycle budget
    app/events/projectors.py:1325  project_producer_rails
    app/events/projectors.py:1140  _apply_attributable_signal_event
```

`project_read_models` raises identically, so the replay/parity verifier and audit harness are affected too.

This is not corruption being correctly rejected. **Pre-R6a nothing enforced the budget**: `core.py` at
`6955208` stamps `cycle_budget_limit` into payloads and contains **zero** references to `consumed`. An
over-budget log is the *normal* prior state.

**A second, far more ordinary trigger** raises the likelihood substantially — simply changing the operator's
budget setting between two ingests:

```
   1 signal_quarantined limit= 5
   2 signal_quarantined limit= 8
ProjectionError: signal_quarantined event sequence=2 has cycle_budget_limit=8, expected pinned value 5
```

Two invalid signals and one config edit is enough. The failure occurs at `initialize()`, before anything is
reachable, and there is no skip, quarantine, or repair path — **order, fill, position and session truth all
become unopenable**, permanently, on an append-only log.

It is **flag-independent**. `D-R6a-14` scoped flag-off safety to "the HTTP surface only" and disclosed that
the *DDL* runs flag-independently; that the *fold* also runs flag-independently and **fail-closed** was
neither disclosed nor ratified. `tests/test_signal_sqlite_schema.py:196` proves the DDL lands on a legacy
database, but that fixture contains no event log, so the branch has no test for this at all.

*Reachability, stated fairly:* routes are flag-off by default and flag-on needs a provider that does not
exist after R6a, so a stock operator database should hold zero signal events. Exposure is dev and CI
databases and anything built through the `build_flag_on_app` seam. That is why this is P1, not P0.

**Required:** ratify one of — (a) a recorded R6a watermark below which the strict invariants do not apply;
(b) a bounded per-producer startup quarantine that records the fact and refuses that producer without
refusing the store; (c) an explicit, tested refusal naming the producer, sequence and remedy. Whichever is
chosen, add a pre-R6a-corpus test generated on `6955208` and opened on the branch, covering **both**
triggers — over-budget count and a changed limit within one cycle.

### R-2 (P1) — O(global log) on the single-writer lock

**Reproduced by the review seat.** Cost per attributable rejection grows linearly with **total** log size —
the global execution log, containing orders, fills and positions, not just signals:

```
log=   100 : 10 attributable rejections in    55.4 ms  (  5.54 ms each)
log=  2000 : 10 attributable rejections in   354.2 ms  ( 35.42 ms each)
log= 10000 : 10 attributable rejections in  1405.9 ms  (140.59 ms each)
```

The scan sits inside `async with self._lock`, which serialises every order and fill write. At the default
`signal_invalid_budget_per_epoch = 50`, one producer burning its budget costs ~7 s of exclusive writer time
at a 10k log. A lens measured up to **three** full scans per `release_producer` call.

The implementer knew the hazard and pinned two hot paths against it —
`test_received_signal_materialization_does_not_scan_the_global_log:125` and
`test_quarantined_rate_check_does_not_rescan_event_log:259` — but left unpinned the one path that folds.
The repo already gates this class in `tests/test_wo0113_repair_scaling.py`.

**Required:** bound the fold — from the last `PRODUCER_RELEASED` for that producer, or via an authoritative
per-producer watermark — or record an explicit ratified scaling disclosure. Add a rejection-path scaling pin
mirroring the accepted-path one. R6b inherits this at the step-4 call site.

### R-3 (P2) — release_producer: different authority per store

Found independently by all three lenses. Memory reads the **log fold** (`memory.py:5922`); SQLite reads the
**cached row** and additionally runs `_authoritative_epoch_sequence_locked` (`sqlite.py:8154`, `:8162`).
Under identical injected drift, in both directions:

```
Drift A — cache CLOSED, log OPEN:  memory: release SUCCEEDED   sqlite: ProducerNotQuarantinedError
Drift B — cache OPEN, log CLOSED:  memory: ProducerNotQuarantinedError   sqlite: InvalidEventError
```

**Memory fail-opens where SQLite fail-closes**, on a human-gated operator surface, and the two error types
map to different HTTP codes in R6b. CLAUDE.md makes dual-store parity mandatory for this class.
**Required:** both stores gate on the same source and both run the agreement check; add a dual-store pin
under a divergent rail.

### R-4 (P2) — an inescapable 403

Reachable from a legacy log at exactly the limit. The gate is `epoch_open OR consumed >= effective_limit`,
but `release_producer` — the only exit — requires `quarantine_epoch_open`. Raising the configured budget
does not help, because `effective_cycle_budget_limit = pinned_limit or cycle_budget_limit` keeps the pinned
value. The producer is permanently 403'd with no operator remedy. **Required:** let `release_producer` accept
a closed-epoch producer at or over its pinned limit, or fail closed at `initialize()` on
`consumed >= limit ∧ ¬epoch_open` so the state can never be served.

### R-5 (P2) — an append-only log validated against mutable constants

`projectors.py:917-940` lazily imports four names from `app.store.core`, dodging a real package-init cycle;
`lint-imports` is blind to it. Two of them — `SIGNAL_RATE_BURST_MAX`, `SIGNAL_REJECTED_COUNT_MAX` — are used
as **replay-validation upper bounds**. Lowering either later retroactively invalidates already-written
events and bricks startup: the same class as R-1.

*Reviewer disclosure:* this exposure traces to a planning-seat instruction. War-game pass 5 F-3 required
these caps be **public so R6b's `config.py` imports rather than re-declares** them — which is precisely what
makes them mutable-by-config while serving as log-validation bounds. The instruction was right about
duplication and did not think through the second-order effect. **Required:** move the four constants to
`app/models.py` (contract 4 already forbids kernel-to-layer dependencies, so the cycle disappears and both
sides import eagerly), and record that **lowering a ratified cap is a log-truth change, not a config
change.**

### R-6 (P2) — the gate trusts the cache unchecked

`_authoritative_epoch_sequence_*` runs only when an opener is proposed, on rate breach, and on release. With
the cache saying closed and the log saying open, a **valid** ingest is accepted and appends `SIGNAL_RECEIVED`
inside an open epoch — against `ADR-009:343-345` — and because `SIGNAL_RECEIVED` is non-attributable, the
fold's guard never fires. An attributable rejection *is* caught and rolls back. **No R6a path desynchronises
the two, so this is not live today** — but R6b adds sweeps that write producer-level events. **Required:**
cross-check in the gate, or record an explicit R6b constraint that every producer-level event is written
through a rail method that refreshes the cache — and pin it.

### R-7 to R-13 (P2/P3)

- **R-7** — `SIGNAL_INVALID_BUDGET_HARD_CAP` (`config.py:47`), `_SIGNAL_CYCLE_BUDGET_MAX` (`core.py:5610`),
  new `_PRODUCER_CYCLE_BUDGET_MAX` (`projectors.py:913`), new bare literal `1000` (`sqlite.py:1460`). The
  three *new* caps were single-sourced correctly; the *old* one was duplicated twice more. Add it to the
  contract import tuple and delete both copies.
- **R-8** — `tests/test_signal_rails_core.py:245-251` scans `Path("app/store")`, which resolves to nothing
  off-root and passes vacuously. This is the **only** enforcement of the store→facade prohibition, since
  `lint-imports` provably cannot see it. Anchor to `Path(app.store.__file__).parent` and assert the scanned
  list is non-empty.
- **R-9** — mutating the gate to `if producer_rail.quarantine_epoch_open:` alone leaves the entire signal
  corpus GREEN. The other direction goes RED, so the pin is half-covered rather than inert. Add a synthetic
  pin seeding `consumed == limit, epoch_open = 0`, or record the branch as intentionally defensive.
- **R-10** — `routes_signals.py:201` branches on `result.record is None`; any future record-free outcome
  would be labelled "producer is quarantined". Key on `SignalIngestOutcome.PRODUCER_QUARANTINED`.
- **R-11** — `_upsert_producer_log_rail(cur, rail: object)` reads seven durable columns via `getattr` string
  lookups; `mypy` cannot check any of it, and the two callers pass different types. Declare a `Protocol`.
- **R-12** — `tests/test_signal_ingest_properties.py:80` passes `producer_rail=None` on every plan, so the
  R4 property corpus only ever exercises the zero rail. Parameterise a slice.
- **R-13** — `_producer_rail_contract()` re-executes its import per fold event. Memoise. The cycle-avoidance
  rationale is genuine; only the call frequency is wrong.

---

## What could not be broken

Recorded because a clean bill is only worth what the probing behind it is worth.

**Truth-model partition (`D-R6a-3`) — correct, and structurally so.** `ProducerRailProjection`
(`projectors.py:995`) *omits* the bucket fields, and `rejected_count` has no durable column at all. The
exclusion cannot be silently violated because the fields do not exist on the projection type. Class-A
rebuild and class-B preservation hold on both stores across restart, including non-UTC offsets and
microseconds. No state was found where the rebuild overwrote the bucket or lost class-A state. At the SQL
level the two upserts write **disjoint column sets** on their conflict paths, so preservation is a property
of the schema rather than of discipline.

**Replay registration (`D-R6a-3.7`) — correct and NOT inert.** Not a REV-0039 recurrence: deleting
`producer_rails=project_producer_rails(...)` from `project_read_models` goes RED, and so does deleting the
`producer_rails` loop from `_describe_read_model_diff`. Both halves are pinned.

**Atomicity (`D-R6a-2`) — correct.** `_atomic()` is **16 snapshot / 16 restore**, balanced, with all three
new rail collections in both halves; each removed individually goes RED. *Minor gap:* bucket rollback is
caught only by the synthetic sentinel test, not by the real-mutation rollback test — worth a one-line
extension.

**The unpredicted repairs — could not be broken.** The direct-materialize path is equivalent to the fold it
replaced, verified by reading and then by **differential fuzz: 25 seeds × 60 ops × both stores, comparing
live class-A against the fold after every operation, 0 failures**, plus a 12-step hand-built mixed sequence
agreeing at all 13 checkpoints. The clock-regression guard refuses before any mutation on both stores, and
prevents a **false quarantine**, not merely an over-credit. The lazy constant load dodges a genuine cycle
(restoring the top-level import reproduces `ImportError: partially initialized module`).

**`D-R6a-9` transition builder — stronger than specified.** Identity-only payload, per-transition dedupe
prefix, and **both fold exclusions enforced at construction**: snapshot-free `SIGNAL_QUARANTINED` requires
`quarantine_reason='producer_sweep'`; `SIGNAL_EXPIRED` requires `sweep`/`conversion`, never `ingest`. The
transition vocabulary is exactly `{SIGNAL_QUARANTINED, SIGNAL_EXPIRED}`, closing the approve/reject leak.

**The DDL as landed is byte-identical to the approved text**, with the R4-style exact-column and UNIQUE
startup guard at `sqlite.py:1146-1172`. Invariants the schema cannot express are enforced at the read
boundary — the paired-bucket rule (`(tokens is None) != (refill_anchor is None)` → `InvalidEventError`),
finite/range checks against the public burst cap, closed-epoch residue, and the ratified `breach_trigger`
vocabulary.

**Mandated decisive mutations — all live, re-run independently by two lenses:**

| Mutation | Result |
|---|---|
| Gate weakened to `consumed >= limit` (the kickoff's named wrong build) | **RED** — 3 tests, both stores |
| Opener not conditioned on the terminal append writing | **RED** — both stores |
| Two-sided fail-closed opener check removed | **RED** |
| Identity swapped for `sequence` | **RED** — both stores |
| Record-free 403 branch removed | **RED** — `assert 500 == 403` |
| Fractional refill truncated (D-R6a-16.4) | **RED** — 4 tests, both stores |

The carry pin paces at 0.75× the token interval — the sub-interval shape `D-R6a-16.4` demanded, not the
1.5× shape it forbade as inert.

**Scope and close-out discipline — clean.** No forbidden path touched. Exactly the two authorized
existing-test edits; the seven `plan.event` tripwire sites untouched, so `event` was not retyped. Status
`REVIEW`, six stale doc claims refreshed, `pkl/` change-log entry added, ledger untouched, nothing moved to
completed, no `result.md` authored by the implementer.

## Gates reproduced by the review seat

Full CI-equivalent run watched to completion on its real exit code, not a wrapper's:

- **4,697 passed · 11 skipped · 1 xfailed · 0 failed · 0 errors** (4,709 total), reached `[100%]`
- Branch coverage **93.1606%** against the `fail_under = 93.0` floor
- `ruff check .` clean · `mypy app/` **77 files, no issues** · `lint-imports` **6 kept, 0 broken**
- Targeted: 320 tests across the R6a corpus, the schema test, `test_signal_ingest_store`, and the coupled
  `test_route_authorization_matrix` — exit 0

*Method disclosure:* a first full-suite attempt reported two `test_warning_hygiene` failures. Those were the
**reviewer's** invocation error — `-p no:warnings` disables the plugin that file asserts is active — not a
defect; both pass without the flag. In that same run the background wrapper reported exit 0 while pytest
returned 1; only an explicitly written `PYTEST_EXIT` marker caught it. The figures above are from a clean
re-run. The implementer's coverage figure was 93.1658% against the reviewer's 93.1606% — Windows/Linux
branch-execution variance, immaterial, both well clear of the floor.

*Note worth carrying:* the suite is green **because CI builds databases fresh**. Nothing in the corpus opens a
pre-R6a database, which is exactly why a green suite proved nothing about R-1.

## Verdict

**ACCEPT-WITH-CHANGES.**

The delivered logic is correct on every gated surface, the payload conforms exactly to what the operator
ratified, and every decisive pin is live under independent mutation. This is strong work: the implementer
found and fixed six defects the five-pass war-game did not predict, and caught its own near-inert carry pin.

**The review gate does not clear until R-1 and R-2 are dispositioned**, because both are consequences of an
undisclosed departure from the ratified cache-versus-fold design, and R-1 can render an operator's database
permanently unopenable through nothing more exotic than editing a config value. Both trace to a single
decision that belongs to the planning seat and the operator.

R-3 through R-9 should land with the same change. R-10 through R-13 may be carried to R6b if explicitly
recorded in its register.

**D-2a stays OFF.** R6b must not start until this packet is dispositioned.
