---
type: Review Request
rev_id: REV-0044
title: "WO-0104a — Signal Seat R6a rails store surface"
status: STAGED
dispatch_state: READY_FOR_INDEPENDENT_REVIEW
reviewer_seat: Claude
targets: [WO-0104a, ADR-009, signal-seat-r6a]
human_gated_surfaces: [sqlite-schema, event-log-truth, single-writer-store-mutation]
review_base_sha: 6955208ab4888f3d83c11be9eaa97015dcf830ce
head_sha: a6339e1012a7f706a6b1e6e981667d8e85c97dc9
commit_range: 6955208ab4888f3d83c11be9eaa97015dcf830ce..a6339e1012a7f706a6b1e6e981667d8e85c97dc9
branch: codex/signal-r6a-rails-store
created: 2026-07-26
---

# REV-0044 — independent review of Signal Seat R6a

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, the `CLAUDE.md` safety core, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request,
WO-0104a, ADR-009, and the accepted Signal Seat spec/threat-model targets named below. Re-derive
the named properties from the frozen range and fresh local evidence.

Create only `work/review/REV-0044/result.md`. Do not edit this request, implementation, tests,
work-order/state files, accepted specs, PKL, ledger, or another packet. Produce findings only.
Each finding must state defect class, cause, impact, affected `file:line`, what resolves it, and
independent pass/fail evidence. End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or
`ACCEPT`, and list anything not independently verified.

This is authorized defensive assurance of the operator's local Alpaca-Paper stock-management
application. There is no live-trading, external-target, credential-access, persistence, or
network-probing objective. Report at defect level. Do not include reusable evasion instructions,
credential material, exploit payloads, or attack recipes.

## Frozen range and authority

Review exactly:

`6955208ab4888f3d83c11be9eaa97015dcf830ce..a6339e1012a7f706a6b1e6e981667d8e85c97dc9`

The range is one implementation commit:

- `a6339e1` — implement the dual-store R6a rail surface, approved SQLite schema, pure projector
  and replay registration, atomic budget/rate mutation, release primitive, record-free outcome,
  RED/GREEN corpus, PKL trace, and WO close-out to REVIEW.

Authority order is current code/tests, accepted ADR-009 and `docs/spec/signal-seat/`, WO-0104a's
operator-ratified M1/Stop 2 decisions and separately approved Stop 1 DDL, then this request. The
feature flag remains OFF. This packet authorizes review only, not R6b wiring, flag enablement,
merge, PR, completion, disposition, or ledger mutation.

## Boundary to police

R6a owns:

- `app/store/**`: durable producer-rail state; atomic budget debit inside `ingest_signal`;
  atomic per-producer rate check/debit; exactly one quarantine opener per epoch; dual-store
  release/reset; startup reconstruction and validation;
- `app/events/**`: the pure producer-rail projector, replay registration/diff, and the
  snapshot-free sweep/conversion transition builder R6b will consume;
- the approved SQLite table, flag-independent creation, exact-shape/UNIQUE startup guards, and
  schema pins;
- minimal facade/route plumbing for the record-free post-quarantine outcome;
- R6a tests and the dated PKL/work-order evidence trace.

Out of scope and required to remain absent:

- `app/signals_rails_impl.py`, the provider, `SignalRails`, `check_ingest`,
  `is_conforming_rails`, the step-2 consumer call site, and changes to
  `app/facade/signal_rails.py`;
- `app/api/deps.py`, new settings or `.env.example`, in-memory rejected-counter ownership,
  monitoring sweeps, `/api/producers`, the operator release route, cockpit controls, and
  `app/server.py`;
- R7 approve/reject/conversion behavior, flag enablement, live trading, result/disposition,
  ledger mutation, completion move, merge, or PR.

## GAP-08 claim and R6b remainder

The author claims R6a closes only the durable store-mechanics clauses of GAP-08:

- per-producer refilling token-bucket mechanics with REAL fractional carry;
- durable, non-refilling invalid/conflict/DOA cycle-budget accounting;
- atomic debit plus event append and exactly one epoch opener;
- durable dual-store rail reads/rebuild and the release/reset primitive.

GAP-08 as a whole remains open. R6b still owns:

- the real dual-rail provider and the step-2 consumer wiring;
- the best-effort saturating in-memory `rejected_count`;
- settings validation and use;
- expiry/freshness sweeps;
- operator producer-read/release HTTP workflow and cockpit control.

R6a supplies `release_producer(...)`; it does not supply the human-facing release workflow.
Do not disposition GAP-08 as fully closed.

## Stop 1 — approved SQLite DDL and six-item review

The implementer completed setup and Step 0, stopped, presented the following exact DDL plus all
six disclosures, and received explicit operator approval on 2026-07-26 before creating or
altering any table or column:

```sql
CREATE TABLE IF NOT EXISTS signal_producer_rails (
    producer_id TEXT NOT NULL,
    cycle_budget_limit INTEGER,
    cycle_budget_consumed INTEGER NOT NULL,
    quarantine_epoch_open INTEGER NOT NULL,
    quarantine_epoch_sequence INTEGER NOT NULL,
    quarantine_epoch_started_at TEXT,
    quarantine_breach_trigger TEXT,
    rate_tokens REAL,
    rate_refill_anchor TEXT,
    UNIQUE (producer_id)
);
```

Review all six approved items explicitly:

1. The table includes the budget/epoch and token-bucket columns. `rate_tokens` is REAL. On an
   accepted rate check, the stored balance is
   `min(burst, tokens + elapsed_seconds * limit_per_hour / 3600) - 1`, with the anchor advanced
   to `now`; a rejected check preserves both bucket fields.
2. `cycle_budget_limit` is nullable for a rate-only quarantine epoch. The paired
   `rate_tokens IS NULL` / `rate_refill_anchor IS NULL` state means uninitialized or reset-full.
3. `SCHEMA` and `_migrate` run flag-independently, so the table is created in an existing
   operator database while the Signal Seat flag remains off.
4. Startup refuses any exact name/type/nullability/PK mismatch and separately requires the exact
   unique key `UNIQUE(producer_id)`.
5. `tests/test_signal_sqlite_schema.py` pins fresh and legacy creation, exact shape, uniqueness,
   and deterministic refusal of malformed pre-existing tables.
6. The truth partition is per column:
   - log-derived and rebuilt: `cycle_budget_limit`, `cycle_budget_consumed`,
     `quarantine_epoch_open`, `quarantine_epoch_sequence`,
     `quarantine_epoch_started_at`, `quarantine_breach_trigger`;
   - primary durable and preserved: `rate_tokens`, `rate_refill_anchor`.

`rejected_count` is deliberately absent from the schema and remains R6b's best-effort diagnostic.

## Stop 2 — explicit event-log payload review item

The operator ratified this append-only vocabulary on 2026-07-26. REV-0044 supplies the required
independent packet half. Verify that `PRODUCER_QUARANTINED` has:

- common fields only: `producer_id`, `breach_trigger`, ISO `epoch_start`,
  `epoch_sequence`;
- for `breach_trigger == "budget_exhausted"` only:
  `cycle_budget_consumed`, `cycle_budget_limit`;
- for `breach_trigger == "rate_breach"` only: `bucket_capacity`;
- no irrelevant null-valued fields;
- exactly `breach_trigger ∈ {"budget_exhausted", "rate_breach"}`.

Verify that `PRODUCER_RELEASED` has exactly:

- `producer_id`, `actor`, `rejected_count`, `epoch_start`, `released_at`;
- the epoch sequence appears only in the event dedupe key, not in its payload.

Any additional field or vocabulary value is outside the operator's ratification and is blocking.

## Truth-model and live/replay agreement

The live-versus-replay agreement claim applies only to the six log-derived class-(A) columns:

- `cycle_budget_limit`;
- `cycle_budget_consumed`;
- `quarantine_epoch_open`;
- `quarantine_epoch_sequence`;
- `quarantine_epoch_started_at`;
- `quarantine_breach_trigger`.

It explicitly excludes `rate_tokens`, `rate_refill_anchor`, and `rejected_count`. The bucket can
debit on a same-hash replay that appends no event and therefore cannot be reconstructed from the
event log. Review restart behavior for this partition rather than demanding an impossible full-row
replay equality.

Every actually written signal event must materialize class-(A) producer membership live, including
a valid `SIGNAL_RECEIVED`, so live and canonical replay membership agree before and after restart.
Ordinary non-attributable valid writes must not fold the global event log under the single-writer
lock; authoritative folds are reserved for actual budget-debit/opener paths.

## In-store ordering and route coupling

`docs/spec/signal-seat/01-schema.md:86-92` requires boundary rejection before body handling and
before dedupe. Verify that:

- an open epoch or an exhausted pinned budget is rejected before planning/dedupe and appends
  nothing;
- an identical replay inside an open epoch returns the machine-distinguishable
  `producer_quarantined` outcome with no record, rather than a 200 replay;
- both mounted parsed and validation-failure response paths map the record-free outcome to 403
  without attempting model validation on `None`;
- the paced-arrival rail and budget-exhaustion accounting remain within one atomic store
  transaction/lock boundary.

`tests/test_route_authorization_matrix.py:238-247` currently expects a valid producer credential
to avoid 401/403 because each case starts with a fresh app/store. R6a contributes the race-path 403;
R6b's real step-2 provider will add the steady-state rail 403. R6b inherits the obligation to
distinguish authorization 403 from rail 403 in the matrix without weakening role enforcement.
Review R6a against this coupling, but do not implement the R6b matrix change here.

## Named defect closures to verify

| Defect class | Cause | Impact | Implemented control | Primary files |
|---|---|---|---|---|
| schema drift acceptance | SQLite startup previously had no rail table shape or unique-key truth | A malformed durable row could serve incorrect rail state | Approved DDL, exact-column guard, exact `UNIQUE(producer_id)` guard | `app/store/sqlite.py`, `tests/test_signal_sqlite_schema.py` |
| memory rollback omission | `_atomic()` is a manual snapshot/restore enumeration | A failed operation could keep a rail debit while truncating its event | Rail collections added to both snapshot and restore halves; forced-failure parity pin | `app/store/memory.py`, `tests/test_signal_rails_store.py` |
| replay registration omission | A pure projector alone does not place rails in canonical replay | Restart/live comparison could omit the new truth surface | `producer_rails` registered and diffed in replay | `app/events/replay.py`, `tests/test_signal_rails_projector.py` |
| dedupe/write discrimination | append helpers return a stored event for both writes and no-ops | A no-op could receive a debit or contradictory opener | Actual write is decided by returned-vs-proposed event identity under the same lock/transaction | `app/store/memory.py`, `app/store/sqlite.py` |
| open-epoch ingress ordering | Budget exhaustion alone is not equivalent to an epoch being open | A rate-open, zero-consumed epoch could continue appending signals | Gate is `epoch_open OR consumed >= pinned_limit` before planning/dedupe | `app/store/core.py`, both stores, `tests/test_signal_rails_store.py` |
| record-free response crash | Existing facade/route code assumed every outcome had a record | A correct boundary rejection could surface as HTTP 500 | Optional record plus explicit machine outcome/403 branches | `app/facade/signals.py`, `app/api/routes_signals.py`, `tests/test_signal_rails_routes.py` |
| fractional refill loss | Truncate-and-advance discards sub-token credit | Paced arrivals can be rejected earlier than the configured REAL rate | REAL balance and exact fractional carry; sub-interval and bank-then-burst controls | both stores, `tests/test_signal_rails_store.py` |
| clock-regression mutation | Moving an anchor backward can over-credit later checks | Injected non-monotonic time corrupts durable rate accounting | Backward time is refused before mutation | both stores, `tests/test_signal_rails_store.py` |
| cap/projector divergence | Runtime validation and replay validation could use different literals | Stores and replay could disagree on accepted event truth | Public shared caps and projector fail-closed validation | `app/store/core.py`, `app/events/projectors.py` |
| transition/projector mismatch | A builder could mint shapes the projector refuses or later-rung incomplete events | Sweep/conversion events could make replay fail | Builder restricted to replay-valid sweep/conversion transitions with exact vocabulary | `app/store/core.py`, `app/events/projectors.py`, `tests/test_signal_rails_core.py` |
| stale-cache epoch identity | A preliminary opener sequence derived from cached state can exceed authoritative log state | A valid first opener can fail or acquire the wrong epoch identity | Pure proposal is sequence-independent; store replaces it under lock from the authoritative fold | both stores, `tests/test_signal_rails_store.py` |
| class-A membership drift | Live state materialized only events carrying a budget limit | A valid producer appeared only after replay/restart | Every actual signal write materializes validated class-(A) state | both stores, projector tests |
| import-order cycle | Eager store package imports met projector imports of store constants | Fresh projector/replay imports could fail despite suite import order | Lazy single-source rail-contract load with fresh-interpreter pins | `app/events/projectors.py`, `tests/test_signal_rails_projector.py` |
| ordinary-ingest global fold | The first class-(A) repair folded all events for every valid write | Normal ingest became O(total event log) under the writer lock | Direct zero-state materialization for non-attributable writes | both stores, `tests/test_signal_rails_store.py` |

For each row, establish that the regression is behaviorally tied to the control. Temporary local
mutations are allowed for failure-capable verification, but restore the tree before writing
`result.md` and report only defect-level pass/fail evidence.

## Critical properties to re-derive

1. The memory and SQLite stores expose the same validated rail read/list, rate-debit, ingest-budget,
   restart/rebuild, and release behavior.
2. Budget debit, rate debit, opener append, signal append, and rollback obey one single-writer
   lock/transaction boundary; a failure leaves both rail state and event log unchanged.
3. A budget/rate breach creates exactly one opener for the epoch. Later attempts while open append
   nothing and mutate neither budget nor bucket.
4. `cycle_budget_limit` pins on the first attributable rejection and does not change with later
   settings. Rate-only epochs may keep it null.
5. Release requires an open epoch, validates actor/count/time, appends exact event truth, resets both
   rails, increments only through the next opener, and permits a later new epoch.
6. Reject paths preserve the REAL bucket pair. Accepted checks preserve fractional carry.
   Clock regression and invalid/cap-exceeding inputs are read-only failures.
7. Rebuild overwrites only class-(A) columns and preserves class-(B) bucket state. The live/replay
   agreement and exclusions are stated exactly as above.
8. Fresh imports of `app.events.projectors` and `app.events.replay` succeed in either order.
9. No file under `app/store/` imports `app.facade`; `ProducerRateVerdict` is a store DTO, not the
   out-of-scope `RailsDecision`.
10. The only existing-test edits are the sanctioned planner kwarg in
    `tests/test_signal_ingest_properties.py` and the DDL coverage in
    `tests/test_signal_sqlite_schema.py`; the seven `plan.event` reads remain untouched.
11. No R6b/R7 implementation, new settings, forbidden-path edit, flag enablement, live-trading
    change, accepted-spec change, ledger entry, result/disposition, completion move, merge, or PR
    appears in the frozen range.
12. Alpaca Paper-only, submitted-is-not-filled, fill-only position mutation, backend truth
    ownership, kill-switch enforcement, and the single-writer engine remain unchanged.

## Required mutation evidence to reproduce skeptically

The author reports these temporary mutations were applied, observed RED, restored, and then GREEN:

| Control removed or changed | RED evidence at defect level | Restored evidence |
|---|---|---|
| open-epoch half of the ingest gate | Both stores allowed the rate-open/zero-consumed case to leave the required quarantine outcome; the identity-replay pin also changed outcome | Focused dual-store gate pins GREEN |
| REAL carry changed to truncate-and-advance | Both stores lost banked fractional credit; bank-then-burst ended at 0 instead of 5 | Sub-interval and bank-then-burst pins GREEN |
| memory bucket restore field | Forced exception left durable/in-memory rail state changed | Full rail/event rollback GREEN |
| SQLite rollback replaced with commit | Forced exception retained a real rail update | Full rail/event rollback GREEN |
| replay registration removed | Canonical replay lacked the producer rail | Registration pin GREEN |
| actual-write identity check removed | A no-op attempted a contradictory opener and the fold failed | Dual-store no-op pins GREEN |
| record-free route branch removed | Mounted response became HTTP 500 rather than rail 403 | Parsed and validation-failure route pins GREEN |
| exact-column, UNIQUE, or table-creation guards removed | Malformed/legacy schema controls failed | Ten schema tests GREEN |
| shared bucket cap raised from 100 to 101 | Projector accepted an above-cap event | Four cap cases GREEN |
| clock-regression guard removed | Both stores mutated/accepted regressing time | Dual-store read-only refusal GREEN |
| transition vocabulary/shape validation removed | Invalid or later-rung incomplete events were built | Builder/projector pins GREEN |
| authoritative opener sequence replacement removed | High stale cache blocked the first opener in both stores | Epoch sequence 1 in both stores |
| every-write class-(A) materialization removed | Live/replay membership controls failed 3/3 | Pre/post-restart membership GREEN |
| lazy contract import removed | Fresh projector import failed with a partially initialized module | Fresh projector/replay imports GREEN |
| direct non-attributable materialization removed | Ordinary valid ingest invoked the global projector in both stores | No-projector dual-store control GREEN |

The first two rows are the work order's two pre-identified inert-pin risks. Do not accept the
unmutated GREEN result alone for either one.

## Author evidence to reproduce

- Setup gate: clean tree; `git fetch origin`; both required `git cat-file -e` probes exit 0;
  branch based on `origin/master` SHA
  `6955208ab4888f3d83c11be9eaa97015dcf830ce`.
- All eight Step 0 premises were reported before code; all four P0 premises matched WO-0104a.
- Stop 1: exact DDL and all six items presented, then explicitly approved before DDL mutation.
- Focused R6a plus schema corpus: `126 passed`.
- Complete 14-file signal corpus: `335 passed` in 14.50 seconds.
- Final uninterrupted full branch-coverage suite: `4,697 passed, 11 skipped, 1 xfailed` in
  647.56 seconds.
- Exact coverage: `93.1658%`, up `0.0458` percentage points from the Step 0 baseline `93.12%`,
  above the configured 93.0% floor.
- R2 conformance oracle: `61 passed`.
- WO-0113 repair-scaling: `13 passed`.
- `ruff check .`: `All checks passed!`.
- Scoped `ruff format --check`: `15 files already formatted`.
- `mypy app`: `Success: no issues found in 77 source files`.
- `lint-imports`: 6 kept, 0 broken.
- `harness/bootstrap.py`: exit 0; dependencies satisfied; Ruff/mypy/4,709-item collection
  completed. Restricted-network pip retries were non-fatal.
- Ledger, disposition, PKL, install, version, work-order scope, forbidden-path, store/facade grep,
  and `git diff --check` gates: passed.
- An independent implementation audit returned ACCEPT with no unresolved findings after its three
  late defects were fixed and pinned. This does not substitute for REV-0044.

No `INV-*` entry was added or amended in the frozen range.

## Curated targets and exclusions

Implementation:

- `app/store/base.py`
- `app/store/core.py`
- `app/store/memory.py`
- `app/store/sqlite.py`
- `app/events/projectors.py`
- `app/events/replay.py`
- `app/facade/signal_commands.py`
- `app/facade/signals.py`
- `app/api/routes_signals.py`

Primary R6a regressions:

- `tests/test_signal_rails_core.py`
- `tests/test_signal_rails_projector.py`
- `tests/test_signal_rails_store.py`
- `tests/test_signal_rails_routes.py`
- `tests/test_signal_sqlite_schema.py`
- `tests/test_signal_ingest_properties.py`
- inherited signal and full-suite tests

Authority/state:

- `work/queue/WO-0104a-signal-rails-store-surface.md`
- `work/active/SIGNAL-R6a-STATE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/01-schema.md`
- `docs/spec/signal-seat/02-lifecycle.md`
- `docs/spec/signal-seat/03-rails.md`
- `docs/spec/signal-seat/04-auth-and-api.md`
- `docs/THREAT_MODEL_SIGNAL_SEAT.md`
- `pkl/architecture/signal-seat.md`

Out of scope: R6b provider/wiring/settings/sweeps/operator UI, R7 conversion, feature enablement,
live trading, real credentials, result/disposition, ledger, completion move, merge, PR, and fixes
by the reviewer.

## Expected output

Write findings only to `work/review/REV-0044/result.md`, followed by one verdict. `BLOCK` any
safety-invariant breach, unapproved schema or payload vocabulary, non-atomic debit/event truth,
duplicate epoch opener, open-epoch signal append, bucket restart reset, replay/live class-(A)
disagreement, accepted-path fractional loss, read-only rejection mutation, record-free 500,
inert decisive regression, startup schema acceptance, R6b/R7 scope leak, flag enablement,
forbidden-path change, or completion evidence that cannot be independently reproduced.
