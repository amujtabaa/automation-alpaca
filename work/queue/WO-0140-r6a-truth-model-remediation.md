---
type: Work Order
title: "R6a-R — rails truth-model remediation: cache-authoritative live path, release-boundary bounded folds, tolerant startup, release as the universal recovery"
status: DRAFT
work_order_id: WO-0140
remediates: "work/review/REV-0044/result.md R-1..R-13 (WO-0104a, held in REVIEW)"
branch: codex/signal-r6a-rails-store (remediation commits on the same branch, per REV-0042/0043 precedent)
model_tier: strong (LOCAL Codex — event-log truth, human-gated release semantics, single-writer hot path)
review: "REV-0044 addendum re-review clears the gate; the ADR/spec amendment is a NAMED item in it"
wargame: "FULL per .ai-os/core/18 — M4b pass complete (10 findings: 1 P0, 3 P1); rev-2 applies all ten"
filter_risk: LOW-MED
---

# WO-0140 (rev-2) — R6a-R: the truth-model remediation

> **rev-2 (2026-07-27).** The M4b pass returned **10 findings including 1 P0** — and the P0 landed in
> rev-1's own pre-M4b amendment: the checkpoint machinery was internally inconsistent (R-2's checkpoint
> was the last opener, R-3's was the release; sequence-adoption existed only at one of them; and
> `last_known_epoch_sequence` had no evaluable source after heal-plus-restart). Followed literally it
> either exploded at the checkpoint under the delivered appliers or re-emitted a **colliding epoch
> sequence whose dedupe no-op fails closed forever** — a stuck state the "universal recovery" could not
> reach, invisible to both pinned corpora because pre-R6a logs contain no openers. **The direction
> survived; the checkpoint did not.** rev-2 re-founds it on one measured fact: the delivered release
> applier **preserves `quarantine_epoch_sequence`** (its `replace()` omits it), giving the design a
> durable sequence carrier that makes the opener appliers work **unchanged**.
>
> **The one decision (operator ratifies by pasting):** the rail cache is **authoritative for live
> gating**; the log remains the source of truth it verifies against — verification at **epoch
> boundaries and startup only**, bounded to the producer's events **after its last `PRODUCER_RELEASED`
> (exclusive)**, seeded from the durable rail row. Startup is **tolerant per producer**.
> `release_producer` is the **single human recovery** for every stuck rail state, including a
> **no-epoch (zero-width-window) release** that consumes the next epoch sequence. The ADR/spec text
> this invalidates ships in the same change and is a **named item in the REV-0044 addendum**.

## Measured premises (planning seat; rev-2 items re-verified against `b48235e` on 2026-07-27)

1. `PRODUCER_RELEASED`'s **payload** carries no `epoch_sequence` (`producer_id, actor, rejected_count,
   epoch_start, released_at`) — but (premise 6) its **builder** requires one anyway.
2. The fold bounds two payload numbers against mutable caps (`bucket_capacity` vs `rate_burst_max`;
   `rejected_count` vs `SIGNAL_REJECTED_COUNT_MAX`) — and (premise 8) the **row validator** does it too.
3. `models-is-a-leaf` (`.importlinter`) forbids `app.models` importing any layer — the constants
   relocate there legally, imports go eager, the lazy loader is deleted.
4. The appliers are separable functions — **but partially refuted (M4b F-1):** a budget-exhaustion
   opener's applier **reads budget arithmetic** (`consumed != current.cycle_budget_consumed`,
   `projectors.py:1210-1218`), so `PRODUCER_*` events are *readable* from an invalid prefix (payloads,
   sequences) while their *appliers* are not runnable from a mid-cycle checkpoint. Checkpoints must be
   **cycle boundaries**, nothing else.
5. `epoch_start` is load-bearing at four layers — **corrected (M4b F-10):** the fold's *first* blocker
   for a no-epoch release is `if not current.quarantine_epoch_open: raise` (`projectors.py:1242-1246`),
   before any equality check is reachable.
6. **(New, M4b F-3.)** `producer_released_event` requires `epoch_sequence ∈ [1, 2^63−1]` for its dedupe
   key `producer_release:{producer}:{sequence}` (`core.py:6154-6166`) even though the payload omits it —
   a **fifth layer** premise 5 missed. A wedge producer's sequence is 0; the no-epoch release therefore
   needs a ratified key rule (D-R/R-3 below).
7. **(New — the linchpin.)** `_apply_producer_released`'s `replace()` resets `cycle_budget_limit`,
   `cycle_budget_consumed`, `quarantine_epoch_open`, `quarantine_epoch_started_at`,
   `quarantine_breach_trigger` and **omits `quarantine_epoch_sequence`** — the sequence survives release
   in fold state, and the rail row persists it durably. Seed a post-release fold with the row's sequence
   and the delivered opener checks (`expected = current.quarantine_epoch_sequence + 1`,
   `projectors.py:1183-1188`) pass **unchanged**.
8. **(New, M4b F-4.)** `_producer_rail` (`sqlite.py:1503` region) raises unless
   `0.0 <= tokens <= SIGNAL_RATE_BURST_MAX`, and `sqlite.py:1460` carries a bare `1000` — the R-5
   retroactive-brick class exists **below the fold**, in the row validator, against durable class-B
   state no rebuild can heal.

## Decision block (pre-checked = ratified on paste; edit a line to override)

- [x] **D-R — R-1: startup is TOLERANT PER PRODUCER; fail-closed per store only for the unattributable.**
      `project_producer_rails` catches `ProjectionError` **per producer**, marks that producer
      **poisoned** (in-memory, log-derived: producer_id, offending sequence, reason, and
      `last_known_epoch_sequence` = the max **payload** `epoch_sequence` among its readable `PRODUCER_*`
      events — payload, not `event.sequence`), and continues. The marker is DERIVED state — identical on
      both stores and on replay, so parity holds by construction; no DDL, no vocabulary, no durable
      record. **The tolerant fold also writes `last_known_epoch_sequence` into the rail row's
      `quarantine_epoch_sequence` column** — the durable carrier the heal path reads (premise 7).
      **Scoped exception (M4b F-5):** an event whose `producer_id` is itself unreadable
      (`projectors.py:1012-1016`) fails **before attribution** — there is no producer to poison; that
      stays a store-wide refusal, disclosed here. Not producible by any `6955208` writer, so the pinned
      claim is: **`initialize()` succeeds on any `6955208`-producible log.**
      **Poisoned-surface semantics (M4b F-9), all four stated:** ingest and rate checks reuse
      `SignalIngestOutcome.PRODUCER_QUARANTINED` / verdict `"quarantined"` → the existing record-free 403
      (**no new vocabulary — the stop conditions hold**); `ProducerRateVerdict.rail` (non-Optional) and
      `get/list_producer_rails` serve the rail row as persisted (zeros + carried sequence), never a fold;
      `ReadModelProjection` gains a **`poisoned_producers`** field (additive, like `producer_rails` was)
      and `_describe_read_model_diff` compares it — parity covers the marker itself.
      **Pins:** both REV-0044 reproduction corpora (over-budget; changed-limit-mid-cycle) open, poison
      exactly the offending producer, leave all else intact; `project_read_models` returns the identical
      poisoned set (both stores); delete the `poisoned_producers` comparison ⇒ RED (the REV-0039 class).

- [x] **D-R — R-2: the debit becomes INCREMENTAL; folds retreat to boundaries; the CHECKPOINT is the
      last `PRODUCER_RELEASED`, EXCLUSIVE — never an opener (⚠ M4b P0 fix).** rev-1 checkpointed on the
      last opener; measured, that cannot work: the opener's own applier re-checks budget arithmetic whose
      evidence lies before the checkpoint (premise 4) and demands `current+1` sequence continuity
      (premise 7's anchors). **A release is the only true cycle boundary** — after it, budget state
      legitimately folds from zero. The bounded verification fold therefore: starts **after** the
      producer's last `PRODUCER_RELEASED` (from genesis if none — a never-released producer's whole
      history *is* the current cycle, disclosed as unbounded-by-design for that case); is **seeded** with
      the durable rail row's `quarantine_epoch_sequence`; and runs the delivered appliers **unchanged**
      (`:1183-1188` and `:1210-1218` both pass by construction — enumerate in the diff that they did not
      change). The SQL filter must match **both** payload locations (`$.producer_id` **and**
      `$.record.producer_id`) or the bounded fold silently under-counts.
      **Live path:** cache-authoritative gating; the debit updates the cached counters in the same
      atomic op as the append, conditioned on `stored.id == plan.event.id` (unchanged, pinned). **The
      memory store has NO budget-counter cache today** (`memory.py:272-273` holds only epoch sequences
      and rate buckets; `_projected_producer_rail_unlocked` folds live) — R6a-R adds
      **`_producer_budget_rails`** (M4b F-7), which joins **both halves** of `_atomic()`'s enumeration
      with a drop-one-field mutation pin (the parent D-R6a-2 P0 class).
      **Honest cost claim (M4b F-6):** the DEBIT path must flatten — it folds nothing; pin it with the
      repo's scaling-gate pattern. The epoch-boundary and release folds remain **linear filtered scans
      inside the writer lock** (measured ~9 ms at 10k, ~36 ms at 40k rows; the stop conditions forbid the
      index that would bound them) — at most 2 per epoch. **That residual cost is a RATIFIED SCALING
      DISCLOSURE** (the alternative REV-0044 R-2 itself offered), recorded here and in the addendum
      evidence; "must flatten" applies to the debit path only.
      **Pins:** rejection-path scaling pin (debit reads no unrelated log rows); cache == bounded fold ==
      unbounded fold at every boundary of a mixed 12-step sequence, both stores; the R-2 measurement
      flattens on the debit path.

- [x] **D-R — R-3 + R-4: `release_producer` is the ONE human recovery, identically on both stores —
      with the no-epoch release fully specified this time. ⚠ HUMAN-GATED AMENDMENT, ratified by the
      operator pasting this WO; its spec/ADR text refresh ships in the same change (M4b F-8):**
      `02-lifecycle.md`'s release row ("closes the epoch … epoch window") and ADR-009's "one summary on
      epoch close" gain the no-epoch case; **that ADR amendment is a NAMED review item in the REV-0044
      addendum** — one packet, independently reviewed, honoring the cross-model-review rule's substance;
      the operator ratifies this reconciliation by paste.
      Release accepts, both stores reading the **cache** cross-checked by the **bounded fold** (the
      SQLite `_authoritative_*` shape — which compares **all five fields including consumed**, a drift
      net the redesign must and does preserve — adopted by memory):
      1. an **open epoch** (unchanged, exact `epoch_start` equality as today);
      2. the **R-4 wedge** (`consumed >= pinned_limit ∧ ¬epoch_open`) — resetting the cycle;
      3. a **poisoned producer** — the release IS the new fold boundary: **release heals.**
      **The no-epoch (zero-width) release, complete ruling:** payload `epoch_start = released_at`
      (never null; ratified-field domain gains one degenerate case); `rejected_count` 0 unless R6b's
      live holder has a count; **the release consumes the NEXT epoch sequence** — builder key
      `producer_release:{producer}:{row_sequence + 1}` (satisfying premise 6's `>= 1` bound even from a
      wedge's 0), and the fold **advances `quarantine_epoch_sequence` by one** on a no-epoch release so
      live row and fold stay equal. Two heals of one producer thus key distinctly (M4b F-3's collision),
      and the next opener continues at `current+1` unchanged. Changed lines enumerated in the diff:
      `projectors.py:1242-1269` (state-conditional acceptance + sequence advance) and `core.py:6154`
      region (the no-epoch key rule). **Fold-side acceptance of a zero-width release from zero state is
      an accepted weakening, stated plainly:** the fold cannot see live gating; legitimacy is enforced at
      `release_producer` (which still refuses anything outside states 1–3), and the zero-width form is
      machine-recognizable in audit.
      **Pins (M4b F-2 — the inert-mutation repair):** the named mutation is now the **forged** shape:
      epoch OPEN in fold state, release carrying `epoch_start == released_at ≠ true start` ⇒
      `ProjectionError`, both stores — widen the state-conditional check ⇒ THIS pin goes RED (rev-1's
      wrong-value pin provably could not); wedge → 403 → zero-width release → ingest resumes → next
      opener folds at `current+1`; poisoned → release → `initialize()` folds clean from the boundary;
      two consecutive heals key distinctly; the REV-0044 drift probe yields identical outcomes on both
      stores; revert memory to fold-only gating ⇒ RED.

- [x] **D-R — R-5 + R-7 + R-13 + (M4b F-4): constants to `app/models.py`; the read path — fold AND row
      validator — validates STRUCTURALLY; caps bind at write time only.** As rev-1, plus: the row
      validator's `tokens <= SIGNAL_RATE_BURST_MAX` bound (`sqlite.py:1503` region) and the bare `1000`
      (`sqlite.py:1460`) become structural checks (finite, non-negative, `<= _SQLITE_MAX_SIGNED_INT`) —
      class-B durable state is precisely the state **no rebuild can heal**, so a cap-lowering brick there
      is worse than the fold's. The exactness ratchet is untouched. Standing rule to `pkl/`: **lowering a
      ratified cap is a log-truth change, not a config change.**
      **Pins:** rev-1's cap-lowering refold pin, **plus** write the bucket at cap → lower the constant →
      reopen the store ⇒ must serve (RED today); fresh-interpreter imports (eager); grep pin: the budget
      cap literal appears exactly once in `app/`.

- [x] **D-R — R-6: unchanged from rev-1** (R6b constraint recorded in `pkl/`; the boundary cross-checks
      stay as the divergence net).

- [x] **D-R — R-8..R-12: unchanged from rev-1** (module-anchored non-empty grep pin; the wedge pin is now
      a *designed* state exercised by R-3/R-4's pins; outcome-keyed `_record_response`; the
      `Protocol`-typed upsert; the property-corpus rail parametrisation).

## Stop conditions — report, never self-authorize

Any DDL, schema, or **index** change · any new event payload **field** or vocabulary value (the
zero-width ruling changes a domain, not the field list; `SignalIngestOutcome` gains nothing) · any
durable poisoned record · any weakening of the exactness ratchet or of the five-field drift net · any
existing-test edit beyond the pins named here · R6b surfaces · `app/server.py` · the flag.

## Gate battery

Unchanged from rev-1 (full battery incl. `--cov-branch` floor 93.0), plus: both legacy corpora as
committed fixtures; the debit-path scaling pin; the **forged zero-width** pin; the drift-parity pin; the
row-validator cap-lowering pin; the `poisoned_producers` parity-deletion mutation.

## Close-out

Remediation commits on `codex/signal-r6a-rails-store`; WO-0104a stays REVIEW. Stage evidence for the
**REV-0044 addendum**, which must carry as NAMED items: the release-amendment pins (all of them — M4b
F-10), the ADR-009/`02-lifecycle.md` amendment, the ratified scaling disclosure, and the zero-width
payload ruling. The addendum clears the R6a gate; WO-0140 closes atomically (disposition + ledger +
`pkl/` in the finishing commit). D-2a stays OFF; R6b starts only after the addendum disposition.

## §M4b record — pass 1 on this WO (10 findings: 1 P0, 3 P1, 5 P2, 1 P3)

*(Three dispatch attempts died on server-side 529s with zero tool calls — investigated and recorded as
capacity, not content. The completed pass ran on the session-model pool.)*

| # | Sev | Finding | Verified | Applied |
|---|---|---|---|---|
| F-1 | **P0** | Checkpoint cluster internally inconsistent: opener checkpoints unbuildable under the delivered appliers (budget cross-check + `current+1` both fail); `last_known_epoch_sequence` unevaluable post-heal; "(0 if none)" re-emits a byte-identical dedupe key ⇒ permanent fail-closed wedge the recovery cannot reach; both pinned corpora blind to it (no openers pre-R6a) | **YES** — planning seat re-read `:1183-1188`, `:1210-1218`, `:1242-1246`; agent probes pasted | R-2 re-founded: release-exclusive checkpoint, durable row-sequence seed, appliers unchanged; premise 4 corrected |
| F-2 | P1 | rev-1's "widen ⇒ RED" mutation was **inert** — the widened mutant passes the named pin and accepts exactly the forged `epoch_start == released_at` drift shape | YES — agent implemented both mutant and pin; REV-0041/0043 class | R-3 pins: the forged shape is now the named mutation |
| F-3 | P1 | The release **builder** requires `epoch_sequence >= 1` for its dedupe key — a fifth layer; a fixed sentinel collides across two heals and fails closed | **YES** — `core.py:6154-6166` re-read | No-epoch release consumes the next sequence; fold advances to match |
| F-4 | P1 | The row validator bounds durable class-B `rate_tokens` by the mutable burst cap — the R-5 brick class below the fold, unhealable by rebuild | **YES** — planning seat had read the same lines in REV-0044 | R-5 extended to the row validator + reopen pin |
| F-5 | P2 | Pre-attribution `ProjectionError` (unreadable `producer_id`) fires before any producer exists to poison | YES — `:1012-1016` | R-1 scoped exception disclosed; claim re-scoped to `6955208`-producible logs |
| F-6 | P2 | "Must flatten" oversold: boundary folds stay linear filtered scans (measured 9→36 ms at 10k→40k); the index is stop-conditioned away; filter must match both payload locations | YES — agent measurements; `EXPLAIN` = SCAN | Debit-scoped flatten + ratified scaling disclosure + dual-location filter |
| F-7 | P2 | Memory has **no** budget-counter cache — the incremental design forces a new collection nobody named, straight into the `_atomic()` P0 class | YES — `memory.py:272-273`, `:330-331` | `_producer_budget_rails` named + both-halves + drop-one pin |
| F-8 | P2 | The amendment invalidates `02-lifecycle.md` + ADR-009 epoch-close text; no refresh shipped; "no new packet" unreconciled with the ADR-packet rule | YES — spec rows quoted | Refresh ships in-change; ADR amendment a NAMED addendum item |
| F-9 | P2 | Poisoned-surface semantics unstated against delivered types (non-Optional `rail`, outcome reuse, `ReadModelProjection` shape, diff comparison) | YES — `base.py:369-373` | R-1 states all four; no new vocabulary |
| F-10 | P3 | Premise-5 mechanism wrong (`:1242` blocks first); addendum evidence list omitted the release pins | YES | Premise corrected; close-out list extended |

**Also surviving attack, per the pass:** R-1's tolerance direction, R-6, R-8..R-12, the zero-width form
itself ("sound and spec-tolerable once ratified"), the cap relocation (models-is-a-leaf verified clean),
and the five-field drift net (`_authoritative_*` compares consumed too — preserved by the redesign).
