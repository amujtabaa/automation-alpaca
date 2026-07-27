---
type: Work Order
title: "R6a-R — rails truth-model remediation: cache-authoritative live path, bounded epoch-boundary folds, tolerant startup, release as the universal recovery"
status: DRAFT
work_order_id: WO-0140
remediates: "work/review/REV-0044/result.md R-1..R-13 (WO-0104a, held in REVIEW)"
branch: codex/signal-r6a-rails-store (remediation commits on the same branch, per REV-0042/0043 precedent)
model_tier: strong (LOCAL Codex — event-log truth, human-gated release semantics, single-writer hot path)
review: "REV-0044 addendum re-review clears the gate; no new packet"
wargame: "FULL per .ai-os/core/18 — M4b pass pending on this draft"
filter_risk: LOW-MED
---

# WO-0140 (rev-1) — R6a-R: the truth-model remediation

> **The one decision (operator ratifies by pasting):** the rail cache is **authoritative for live
> gating**; the event log remains the **source of truth** it verifies against — but verification moves
> from *every attributable rejection* (today: a full global-log fold per debit, R-2) to **bounded
> per-producer folds at epoch boundaries and startup**. Startup becomes **tolerant per producer** instead
> of fail-closed per store (R-1). `release_producer` becomes the **single human recovery path** for every
> stuck rail state. All thirteen REV-0044 findings resolve in this one change; none carry to R6b except
> the R-6 constraint note, which is inherently R6b's.
>
> **What this trades, stated honestly:** the whole-log-fold debit made double-charging *structurally
> impossible* (REV-0044 §root cause). Incremental debits re-expose that risk, and the protection
> returns to the D-R6a-4 identity discriminator and its pins — which REV-0044 verified live under
> independent mutation (identity→sequence swap: RED both stores) — plus the epoch-boundary cross-check
> as the second net. We trade structural impossibility for pinned-and-cross-checked, and buy back an
> openable store and an O(1) hot path.

## Measured premises (planning seat, 2026-07-27 — each verified against `b48235e` before drafting)

1. **`PRODUCER_RELEASED` carries NO `epoch_sequence`** (`core.py` payload: `producer_id, actor,
   rejected_count, epoch_start, released_at`). A bounded fold therefore checkpoints on the producer's
   last **`PRODUCER_QUARANTINED`**, which *does* carry `epoch_sequence` (REV-0044 payload dump).
   **Adding a field to the release payload is REJECTED** — it is a ratified list; a new field is a new
   gated stop (WO-0104a Stop 2 ruling: "any additional field … is a NEW stop").
2. **The fold bounds two payload numbers against mutable caps** — `bucket_capacity` against
   `rate_burst_max` (`projectors.py:~1225`), `rejected_count` against `SIGNAL_REJECTED_COUNT_MAX` — the
   R-5 retroactive-brick sites.
3. **`models-is-a-leaf`** (`.importlinter`) forbids `app.models` from importing any layer, so the
   constants relocate there legally, both sides import **eagerly**, and the lazy
   `_producer_rail_contract()` loader (R-13) is deleted rather than memoised.
4. **The appliers are separable** (`_apply_attributable_signal_event` `:1115`,
   `_apply_producer_quarantined` `:1151`, `_apply_producer_released` `:1237`), so per-producer tolerance
   is implementable in `project_producer_rails`' loop (`:1291`) — and `PRODUCER_*` events remain readable
   from a prefix whose *budget arithmetic* is invalid, because they are applied by different functions.
5. **(Added pre-M4b, 2026-07-27 — refutes this draft's own first release amendment.) `epoch_start` is
   load-bearing at FOUR layers**, so a no-epoch release is unfoldable as delivered: the builder requires
   an aware datetime (`core.py:6141`) and rejects `released_at < epoch_start` (`:6146`); the fold
   requires it parse (`_required_aware_datetime`) and **cross-checks equality** against the fold state's
   `quarantine_epoch_started_at` (`ProjectionError` on mismatch). Null fails the parse; any datetime
   fails the equality check against `None`. The amendment below is written against this measurement.

## Decision block (pre-checked = ratified on paste; edit a line to override)

- [x] **D-R — R-1: startup is TOLERANT PER PRODUCER, fail-closed per store never.**
      `project_producer_rails` catches `ProjectionError` **per producer**, marks that producer
      **poisoned** (an in-memory, log-derived marker: producer_id, offending sequence, reason,
      `last_known_epoch_sequence` = max sequence among its readable `PRODUCER_*` events), and continues
      folding every other producer. `initialize()` always succeeds; order/fill/position/session truth is
      never hostage to a signal prefix. A poisoned producer's ingest and rate checks return the
      write-free 403; its rail row is not served. **The marker is DERIVED state** — re-computed
      identically by both stores from the same log on every `initialize()` and by `project_read_models`
      on replay, so dual-store and live-vs-replay parity hold by construction. **No DDL, no new event
      vocabulary, no durable record** — which is what keeps this WO free of new gated stops beyond the
      release amendment below. `D-R6a-14`'s disclosure is amended: the fold, like the DDL, runs
      flag-independently — now tolerantly.
      **Pins:** the two REV-0044 reproduction corpora — a `6955208`-generated over-budget log AND a
      changed-limit-mid-cycle log — both open, both quarantine exactly the offending producer, both
      leave every other producer and all non-signal truth intact; `project_read_models` on the same logs
      returns the same poisoned set (parity, both stores).

- [x] **D-R — R-2: the debit becomes INCREMENTAL in the same atomic op; folds retreat to epoch
      boundaries and startup.** Live attributable-rejection path: update the cached counters
      **conditioned on the actual write** (the existing `stored.id == plan.event.id` discriminator —
      unchanged, already pinned) inside the same lock/transaction as the append; **no fold**. The
      whole-log fold survives in exactly three places: `initialize()` (once, tolerant per R-1), the
      **opener-proposal cross-check**, and **release** — and the latter two become **bounded**: fold only
      the producer's events at-or-after its checkpoint (last `PRODUCER_QUARANTINED`, else genesis),
      SQL-filtered so non-matching rows are never materialized. Epoch sequence at write time resumes
      from the checkpoint opener's `epoch_sequence` payload (0 if none) — NOT from a release field
      (measured premise 1). Cost: ≤ 2 bounded folds per epoch instead of up to 50 global folds.
      **Pins:** a rejection-path scaling pin mirroring
      `test_received_signal_materialization_does_not_scan_the_global_log` (the debit must not read
      unrelated log rows — the repo's `test_wo0113_repair_scaling.py` pattern); cache == bounded fold ==
      unbounded fold at every epoch boundary in a mixed 12-step sequence, both stores. The R-2
      measurement (5.5→140.6 ms/rejection over 100→10k events) must flatten.

- [x] **D-R — R-3 + R-4 + part of R-1: `release_producer` is the ONE human recovery path, identically
      on both stores.** ⚠ **HUMAN-GATED AMENDMENT — this line changes ratified release semantics and is
      ratified by the operator pasting this WO.** Release now accepts, on **both** stores reading the
      **same** state class (the cache, cross-checked against the bounded fold exactly as SQLite already
      does — memory adopts the SQLite shape):
      1. an **open epoch** (unchanged);
      2. the **R-4 wedge** — `consumed >= pinned_limit ∧ ¬epoch_open` — resetting the cycle, so a
         legacy-created wedge has an exit and the permanent 403 disappears;
      3. a **poisoned producer** (R-1) — the release append becomes the fold checkpoint, so the invalid
         prefix falls out of scope on the next rebuild: **release heals**.
      Anything else still raises `ProducerNotQuarantinedError`, both stores, same type.
      **⚠ The no-epoch release payload (measured premise 5 forces this to be explicit):** a wedge or
      poisoned release carries **`epoch_start = released_at`** — a machine-recognizable **zero-width
      window** — never null (null fails the fold's `_required_aware_datetime`; a ratified field's type
      does not change). The builder's `released_at < epoch_start` check passes on equality untouched.
      The fold's equality cross-check is **state-conditional**: with an open epoch in fold state, exact
      equality against `quarantine_epoch_started_at` is required exactly as today (the drift net stays);
      with no open epoch (wedge, or a release that IS the poisoned-heal checkpoint), the fold accepts
      precisely the zero-width form and nothing else. `rejected_count` on a no-epoch release is **0**
      unless R6b's live holder has a count. **This is a payload-semantics amendment on a ratified field
      (domain gains one degenerate case; the field list is untouched) — ratified by the operator pasting
      this WO, and named as an explicit item in the REV-0044 addendum.**
      **Checkpoint sequence adoption:** a bounded fold that begins at a release checkpoint holds the
      zero state, so it must **adopt the next opener's payload `epoch_sequence`** (validated positive
      and strictly greater than `last_known_epoch_sequence`) rather than incrementing from zero —
      otherwise every post-heal opener mis-folds as a sequence mismatch.
      **Pins:** the REV-0044 drift probe (cache/log divergence, both directions) now yields identical
      outcomes on both stores; wedge → 403 → release (zero-width window) → ingest resumes → the fold
      accepts the release AND the next opener at `last_known+1`; poisoned → release → next
      `initialize()` folds clean; a normal release with a *wrong* `epoch_start` still fails the fold
      (the drift net is provably not weakened — mutation: widen the state-conditional check ⇒ RED).
      Mutation: revert memory to fold-only gating ⇒ the drift pin goes RED.

- [x] **D-R — R-5 + R-7 + R-13: constants move to `app/models.py`; replay validates STRUCTURALLY;
      write-time validates against caps.** `SIGNAL_RATE_LIMIT_PER_HOUR_MAX`, `SIGNAL_RATE_BURST_MAX`,
      `SIGNAL_REJECTED_COUNT_MAX`, the budget cap (single name — `core.py`'s `_SIGNAL_CYCLE_BUDGET_MAX`,
      `projectors.py`'s `_PRODUCER_CYCLE_BUDGET_MAX`, `sqlite.py:1460`'s bare `1000`, and
      `config.py:47`'s `SIGNAL_INVALID_BUDGET_HARD_CAP` all collapse to imports of it), and the two
      vocabulary sets relocate to `app/models.py` (legal per measured premise 3). The lazy loader is
      **deleted**; imports go eager. The fold's numeric upper bounds change from ratified caps to
      **structural bounds** (`_SQLITE_MAX_SIGNED_INT`, non-negative) — an append-only log is never
      re-judged by a mutable constant. The payload-exactness ratchet (`_require_exact_payload_fields`)
      is **untouched**: field *names* stay strict; only mutable *numeric ceilings* leave the read path.
      **Standing rule recorded in `pkl/`: lowering a ratified cap is a log-truth change, not a config
      change.**
      **Pins:** fresh-interpreter imports of `app.events.projectors` / `app.events.replay` (the cycle
      pin, now eager); write a `PRODUCER_RELEASED` at the cap, lower the in-memory cap constant, refold
      ⇒ must still fold (RED today); one `grep` pin asserting the budget-cap literal appears exactly
      once in `app/`.

- [x] **D-R — R-6: the R6b constraint is RECORDED, the backstop stays.** With incremental counters the
      cache is in-sync by construction on every R6a path; the opener-proposal and release cross-checks
      remain as the divergence net. Recorded for R6b (in the WO close-out note AND
      `pkl/architecture/signal-seat.md`): **every producer-level event R6b writes (sweeps) must go
      through a rail method that updates the cache in the same atomic op** — appending via the raw event
      API desynchronises cache from log and the gate will trust the cache.

- [x] **D-R — R-8..R-12 mechanical closures, all in this change:** R-8 — the store→facade grep pin
      anchors to `Path(app.store.__file__).parent` and asserts a non-empty scan (it is the ONLY
      enforcement of that boundary; `lint-imports` is blind to it). R-9 — a synthetic wedge pin
      (seed `consumed == limit, epoch_open = 0` ⇒ boundary 403 ⇒ release succeeds), which the R-3/R-4
      amendment makes a *designed* state rather than a defensive branch. R-10 — `_record_response`
      branches on `SignalIngestOutcome.PRODUCER_QUARANTINED`, not `record is None`. R-11 —
      `_upsert_producer_log_rail` takes a `Protocol` with the six class-A fields, not `object`/`getattr`.
      R-12 — parameterise a slice of `test_signal_ingest_properties.py` over open-epoch and at-limit
      rails instead of `producer_rail=None` everywhere.

## Stop conditions — report, never self-authorize

Any DDL or schema/index change · any new or altered event payload **field** or vocabulary value (the
release payload gains nothing — measured premise 1 makes the design not need it) · any durable record of
the poisoned marker · any weakening of the payload-exactness ratchet · any existing-test edit beyond the
pins named here · anything touching R6b's surfaces (`deps.py`, provider, sweeps, routes, cockpit,
settings) · `app/server.py` · the flag.

## Gate battery

Unchanged from WO-0104a (including `pytest --cov=app --cov-branch`, floor 93.0), **plus**: both legacy
reproduction corpora as committed fixtures; the rejection-path scaling pin; the drift-parity pin. All
Fable v3: RED first, pasted evidence, mutation checks on every decisive pin — REV-0044's mutation table
is the template.

## Close-out

Remediation commits on `codex/signal-r6a-rails-store`. WO-0104a stays REVIEW. Stage the evidence for a
**REV-0044 addendum** re-review (the review seat re-runs: both legacy corpora, the scaling measurement,
the drift probe, the cap-lowering refold, and the full mutation table). The addendum — not this WO —
clears the R6a gate. WO-0140 closes with disposition + ledger line + `pkl/` update **in the finishing
commit**. D-2a stays OFF; R6b starts only after the addendum disposition.
