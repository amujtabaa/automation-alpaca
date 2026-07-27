---
type: Work Order
title: "R6a-R — rails truth-model remediation: cache-authoritative live path, release-boundary bounded folds, tolerant startup, release as the universal recovery"
status: READY
ratified: "2026-07-27 (Ameen) — rev-3 M1 block incl. the release-semantics amendment, the zero-width ruling + never-regress sequence rule, the D-R6a-5 supersession, the no-opener-segment anchoring disclosure, the ratified scaling disclosure, the one-packet ADR reconciliation, and the closed test-edit list. SEAT SWAP confirmed same date: Claude (planning seat) implements; Codex takes the gate-clearing independent review."
work_order_id: WO-0140
remediates: "work/review/REV-0044/result.md R-1..R-13 (WO-0104a, held in REVIEW)"
branch: codex/signal-r6a-rails-store (remediation commits on the same branch, per REV-0042/0043 precedent)
model_tier: strong (LOCAL Codex — event-log truth, human-gated release semantics, single-writer hot path)
review: "SEAT SWAP (Ameen 2026-07-27): the implementer is now the REV-0044 author, so the gate-clearing review moves to Codex — a Codex-owned REV-0045 packet referencing REV-0044, explicit verdict over every named item. No seat reviews its own work."
wargame: "FULL per .ai-os/core/18 — two M4b passes (10 + 10 findings, 3 P0 total); rev-3 applies pass 2"
filter_risk: LOW-MED
---

# WO-0140 (rev-3) — R6a-R: the truth-model remediation

> **rev-3 (2026-07-27).** The scoped second M4b pass returned **10 findings including 2 P0** — both,
> again, in the sequence carrier, and both **measured against the delivered appliers**. rev-2's seed
> rule was correct only at the one instant premise 7 had measured (just after a release): the rail row
> advances **at opener time** (`sqlite.py:8118-8121` upserts the fold state right after the opener
> append), so a fold seeded with the row's sequence during an **open** epoch demands `seed+1` of the
> very opener the segment contains — every state-1 release failed closed and every open-epoch restart
> poisoned a healthy producer. And the heal path's marker was **blind to sequences consumed by
> zero-width releases** (the release payload carries none), so a second heal re-minted a byte-identical
> dedupe key — the exact permanent fail-closed wedge this WO exists to eliminate, on the recovery path
> itself. Both fixes are one-line rules; the architecture direction survived both passes.
>
> **Process disclosure for the addendum:** rev-2's pass-1 table carried a false `Verified: YES` — the
> planning seat propagated pass-1's F-7 ("memory has no budget-counter cache") without re-reading the
> anchors. Pass 2 refuted it: **`_producer_budget_rails` already exists** (`memory.py:271`, both
> `_atomic()` halves `:633`/`:658`, gate-read `:5810`), with a delivered drop-one pin. Withdrawn below.
>
> **The one decision (operator ratifies by pasting):** the rail cache is **authoritative for live
> gating**; the log remains the source of truth it is verified against — verification at **epoch
> boundaries and startup only**, bounded to the producer's events **after its last `PRODUCER_RELEASED`
> (exclusive)**, seeded **state-conditionally** from the durable rail row. Startup is **tolerant per
> producer** — including when the *verification itself* finds drift. `release_producer` is the
> **single human recovery** for every stuck rail state; a no-epoch (zero-width-window) release
> consumes the next epoch sequence and **never regresses the durable carrier**. The ADR/spec text this
> invalidates ships in the same change; the reviewer-owned REV-0044 addendum carries an explicit
> verdict over it.

## Measured premises (all re-verified against `b48235e`; pass-2 corrections marked)

1. `PRODUCER_RELEASED`'s payload carries no `epoch_sequence` — **which is exactly why the heal marker
   must never be derived from payloads alone** (pass-2 F-B).
2. The fold bounds two payload numbers against mutable caps; the **row validator** does it too
   (`sqlite.py:1503` region tokens-vs-burst-cap; `:1460` bare `1000`).
3. `models-is-a-leaf` holds; constants relocate to `app/models.py`, imports go eager, the lazy loader
   is deleted.
4. `PRODUCER_*` events are *readable* from an invalid prefix; their *appliers* are not runnable from a
   mid-cycle checkpoint (`projectors.py:1210-1218` re-checks budget arithmetic; `:1183-1188` demands
   `current+1`). Checkpoints must be cycle boundaries.
5. A no-epoch release's first fold blocker is `if not current.quarantine_epoch_open: raise`
   (`projectors.py:1242-1246`).
6. `producer_released_event` requires `epoch_sequence ∈ [1, 2^63−1]` for its dedupe key
   (`core.py:6154-6166`) though the payload omits it.
7. `_apply_producer_released`'s `replace()` omits `quarantine_epoch_sequence` — the sequence survives
   release in fold state and persists in the rail row. **Pass-2 caveat (F-A): the row also advances at
   OPENER time** (`sqlite.py:8118-8121`), so "the delivered appliers pass unchanged" holds only when
   the seed is corrected for an open epoch — see D-R R-2.
8. The row validator bounds durable class-B `rate_tokens` by the mutable burst cap — the R-5 brick
   class below the fold.
9. **(Corrected — pass-2 F-G, planning-seat re-read.)** `_producer_budget_rails` **exists** at
   `b48235e`: `memory.py:271` (init `:315`), both `_atomic()` halves (`:633`/`:658`) with a delivered
   drop-one pin (`tests/test_signal_rails_store.py:52`), debit-path write `:5748`, gate read `:5810`.
   The real memory-side deliverables are two call-site changes: the attributable-debit path's full-log
   `_rebuild_producer_rails_unlocked()` (`memory.py:5746`) becomes an in-place increment, and
   `release_producer`'s fold-read (`:5922`) becomes cache + bounded cross-check.

## Decision block (pre-checked = ratified on paste; edit a line to override)

- [x] **D-R — R-1: startup is TOLERANT PER PRODUCER — including when VERIFICATION ITSELF finds drift
      (pass-2 F-E).** As rev-2 (per-producer `ProjectionError` catch; derived in-memory poisoned marker;
      `last_known_epoch_sequence` written into the rail row's `quarantine_epoch_sequence`; the
      unattributable-event store-wide exception disclosed; claim scoped to `6955208`-producible logs;
      the four poisoned-surface semantics; `poisoned_producers` in `ReadModelProjection` + the diff),
      **plus two pass-2 rules:**
      1. **The five-field cross-check is a poisoning trigger, not a brick.** Under cache authority,
         drift is the design's primary anticipated failure and previously had **no exit**: the delivered
         check raises `InvalidEventError` (`sqlite.py:1571-1578`) — a different type than R-1's catch —
         and `release_producer` re-runs the same check, raising identically on retry. Rule: a boundary
         or startup five-field mismatch **poisons that producer** (catch **both** exception types,
         per producer), funnelling it into release-state 3. Never a store-wide refusal, never an
         unreleasable live wedge. **Pin:** inject the REV-0044 drift probe, restart ⇒ producer poisoned,
         store opens, release heals — both stores.
      2. **Tolerance lives in a WRAPPER** used by `initialize()` and `project_read_models`;
         **`project_producer_rails` itself stays strict** — otherwise the file's eight strict
         `pytest.raises(ProjectionError)` pins and REV-0044's three payload-conformance RED tests invert
         (pass-2 F-D).
      — Marker rule moved to R-3 (never-regress), where its failure mode lives.

- [x] **D-R — R-2: incremental debit; folds at boundaries only; release-exclusive checkpoint with a
      STATE-CONDITIONAL seed (⚠ pass-2 F-A, P0 fix).** The bounded verification fold starts after the
      producer's last `PRODUCER_RELEASED` (genesis if none) and is seeded
      **`seed = row.quarantine_epoch_sequence − (1 if row.quarantine_epoch_open else 0)`** — because the
      row advances at opener time (premise 7 caveat), a flat seed demands `seed+1` of the very opener an
      open-epoch segment contains. With the corrected seed the delivered appliers (`:1183-1188`,
      `:1210-1218`) pass unchanged at **every** boundary, not just the post-release instant. **The
      12-step mixed pin explicitly includes a state-1 (open-epoch) release and an open-epoch restart** —
      the two shapes rev-2's pin would have detonated on.
      **Honest verification scope (pass-2 F-F):** in **no-opener segments** (wedge release, heal, first
      post-release boundary) the seed is a tautology — fold seq == row seq verifies nothing. Add the
      **O(1) structural anchor**: if `row.quarantine_epoch_sequence >= 1`, the log must contain dedupe
      key `producer_release:{p}:{seq}` **or** `producer_quarantine:{p}:{seq}` (exact-key lookups; no
      index, no scan, no new field). Disclose the residual narrowing (the sequence is anchored, not
      re-derived, in those segments) in the addendum rather than claiming full preservation of the
      delivered net. **This supersedes parent D-R6a-5's "the write-time sequence comes from the log
      fold" ruling** — the sequence now comes from the durable row, anchored to the log; the two
      delivered stale-cache pins (`tests/test_signal_rails_store.py:448`, `:496`) are **authorized test
      edits**, re-pinned as *loud fail-closed* (a stale row now raises via the anchor/two-sided checks
      rather than being silently out-derived).
      **Memory deliverables corrected (pass-2 F-G):** `memory.py:5746` rebuild → in-place increment;
      `:5922` fold-read → cache + bounded cross-check. No new collection; the delivered drop-one
      `_atomic()` pin already covers `_producer_budget_rails`.
      **Cost, stated tightly (pass-2 F-J):** the debit path folds nothing (scaling pin as rev-2). A
      never-released producer's boundary fold applies at most `pinned_limit + 1` events (one cycle can
      exist); only the row **scan** is O(global log), identical at every boundary, already priced
      (9→36 ms at 10k→40k). The O(1) release-key lookup may be used to range-bound the scan; the
      **index** remains stop-conditioned. The boundary-fold cost stays a **ratified scaling disclosure**.

- [x] **D-R — R-3 + R-4: the three-state release — with the carrier that NEVER REGRESSES
      (⚠ pass-2 F-B, P0 fix). HUMAN-GATED AMENDMENT, ratified on paste; ADR/spec refresh ships
      in-change.** As rev-2 (three states; both stores gate on cache + bounded cross-check; zero-width
      `epoch_start = released_at`; `rejected_count` 0 unless held; changed lines
      `projectors.py:1242-1269`, `core.py:6154` region; spec/ADR text refresh; fold-side zero-state
      acceptance as a stated weakening), **plus four pass-2 rules:**
      1. **The marker never regresses the durable carrier:**
         `last_known_epoch_sequence = max(row.quarantine_epoch_sequence, max payload epoch_sequence
         among readable PRODUCER_* events)`. rev-2's payload-only rule was blind to sequences consumed
         by zero-width releases (the release payload carries none — premise 1), so poison → heal →
         re-poison **regressed the row** and heal #2 minted a **byte-identical** key
         (`producer_release:{p}:{N+1}`, measured), which `release_producer`'s two-sided check turns into
         a retry-proof raise (`sqlite.py:8175`, `memory.py:5940`) — the recovery permanently wedged.
         **Live `release_producer` explicitly advances the row on a no-epoch release.**
      2. **The genesis-fold heal rule mirrors the write side:** a zero-width release folding in sets the
         sequence to `max(high-water mark at poison, running max opener payload in segment) + 1` — both
         reconstructible at the release point, agreeing with the write side in every traced composition,
         preserving parent D-R6a-3's class-A agreement claim.
      3. **The forged-shape pin is narrowed (pass-2 F-C):** the named mutation is `epoch OPEN in fold
         state **and the producer not poisoned-in-fold**, release carrying
         `epoch_start == released_at ≠ true start`` ⇒ `ProjectionError`. The tolerant wrapper accepts a
         zero-width release for a producer **it has poisoned** regardless of that producer's last
         coherent epoch state — otherwise every legitimate mid-epoch heal re-poisons on every replay, a
         live-vs-replay divergence the fold-vs-fold parity pin structurally cannot see.
      4. **The zero-width fold-acceptance domain is closed (pass-2 F-H):** the fold rejects a zero-width
         release outside **{poisoned-in-fold, wedge, zero state}** — the interior shape
         (`0 < consumed < pinned_limit`, hand-appendable through the raw event seam R6b's sweeps use)
         would otherwise silently launder a partially-consumed budget in replay. The interior shape
         joins the forged-pin family.
      **Pins:** rev-2's set, **plus**: poison → heal → poison (no intervening opener) → heal ⇒ distinct
      keys, both releases land; the narrowed forged shape ⇒ RED on widen; the interior zero-width shape
      ⇒ RED; a poisoned mid-epoch producer heals and **stays healed across replay** (poisoned set empty
      after, both stores).

- [x] **D-R — R-5 + R-7 + R-13 (+ row validator): unchanged from rev-2**, with the **three delivered cap
      pins re-homed as authorized edits (pass-2 F-D):** `tests/test_signal_rails_projector.py:451-487`'s
      `cycle_budget_limit=1001` / `bucket_capacity=101` / `rejected_count=10_001` cases assert
      `ProjectionError` on the read path; under read-structural/write-capped they move to **write-time**
      pins (builder/`_require_bounded_int` level), same values, same RED expectations.

- [x] **D-R — R-6, R-8..R-12: unchanged from rev-1/rev-2.**

## Authorized existing-test edits (closed list — anything else is a STOP)

1. `tests/test_signal_rails_store.py:448` and `:496` — the two stale-cache pins, re-pinned loud
   fail-closed (D-R R-2's supersession of parent D-R6a-5).
2. `tests/test_signal_rails_projector.py:451-487` — the three cap cases, re-homed to write-time.
3. Any pin named in this WO's own pin lists.
`project_producer_rails`' eight strict-raise pins and REV-0044's payload-conformance tests are **not**
authorized — the tolerance wrapper exists precisely so they stand.

## Stop conditions — report, never self-authorize

Any DDL, schema, or **index** change · any new event payload **field** or vocabulary value · any durable
poisoned record · any weakening of the exactness ratchet, the five-field net (beyond the disclosed
no-opener-segment anchoring), or the strict projector · any existing-test edit beyond the closed list
above · R6b surfaces · `app/server.py` · the flag.

## Gate battery

As rev-2, plus: the state-1-release and open-epoch-restart steps in the mixed pin; the double-heal
distinct-keys pin; the narrowed forged pin + interior-shape pin; the drift-poisoning restart pin; the
O(1) anchor pin (corrupt the row sequence in a no-opener state ⇒ loud refusal, not a minted key).

## Close-out

Remediation commits on `codex/signal-r6a-rails-store`; WO-0104a stays REVIEW. **Seat swap in force:**
Claude (the REV-0044 author) implements, so the gate-clearing review is **Codex-owned — REV-0045,
referencing REV-0044** (the reviewer-owns-result rule mirrored, per P-1). The implementer stages
evidence only; **Codex's REV-0045 must carry an explicit verdict over the named items** — the release amendment + zero-width ruling, the ADR-009/
`02-lifecycle.md` amendment, the ratified scaling disclosure, the D-R6a-5 supersession, the no-opener
anchoring disclosure, and the rev-2 F-7 process disclosure — plus `disposition.md` and the ledger line
per the Disposition Loop (pass-2 F-I: a named item clears "for that item" only with its own verdict).
The addendum clears the R6a gate; WO-0140 closes atomically. D-2a stays OFF; R6b starts only after the
addendum disposition.

## §M4b record — pass 2 (scoped to R-2/R-3+R-4; 10 findings: 2 P0, 3 P1, 3 P2, 2 P3)

| # | Sev | Finding | Verified | Applied |
|---|---|---|---|---|
| F-A | **P0** | The seed rule was valid only just-after-release: the row advances at opener time, so every state-1 release failed closed and every open-epoch restart poisoned a healthy producer — then F-C re-poisoned it on every replay | **YES** — planning seat re-read `sqlite.py:8118-8121`; agent measured the applier rejection | State-conditional seed; the two detonating shapes added to the mixed pin; premise 7 caveat |
| F-B | **P0** | The payload-only marker regresses the row across a heal (release payload carries no sequence), so heal #2 mints a byte-identical retry-proof key — the recovery permanently wedged | **YES** — `core.py:6154-6166`, `sqlite.py:8172-8177` re-read; agent measured the collision | Never-regress max rule; genesis heal rule; explicit live row advance; double-heal pin |
| F-C | P1 | The forged-shape pin condemned every legitimate mid-epoch heal on replay — permanent re-poisoning invisible to fold-vs-fold parity | YES — follows from `:1242-1246` + rev-2's pin text | Pin narrowed to not-poisoned-in-fold; wrapper accepts poisoned-producer heals |
| F-D | P1 | rev-2 was unbuildable without unauthorized edits to ≥5 delivered tests; tolerance at `project_producer_rails` would invert 8 strict pins + 3 REV-0044 RED tests | **YES** — both stale-cache pin names read at `:448`/`:496` | Closed authorized-edit list; tolerance wrapper; D-R6a-5 supersession note |
| F-E | P1 | Five-field drift had no ruled exit: `InvalidEventError` escapes R-1's catch and release re-raises it — a fourth stuck state on the primary anticipated failure | YES — `sqlite.py:1571-1578` type read | Drift poisons per producer (both exception types); restart pin |
| F-F | P2 | In no-opener segments the seed is a tautology — the delivered net's independent derivation quietly narrowed exactly where the new release lives | YES | O(1) dedupe-key anchor; residual disclosed in the addendum |
| F-G | P2 | rev-2's premise/F-7 row was **false**: `_producer_budget_rails` exists, enumerated, pinned; the table carried an unverified `Verified: YES` | **YES** — planning-seat re-read `:271,:315,:633,:658,:5748,:5810` | Premise 9; pass-1 F-7 **withdrawn**; process disclosure in the header |
| F-H | P2 | The zero-width acceptance domain was ruled only at its endpoints; the interior shape launders a partial budget in replay via the raw-append seam | YES | Domain closed to {poisoned, wedge, zero}; interior pin |
| F-I | P3 | One-packet reconciliation is protocol-compatible (P-2 "tracked packet", P-1 addenda), but the addendum needs its own explicit verdict + disposition + ledger line, reviewer-owned | YES — protocol clauses quoted by agent | Close-out rewritten |
| F-J | P3 | "Unbounded-by-design" over-disclosed genesis (≤ limit+1 applied events; only the scan is O(log)); the O(1) anchor permits a range-bound without the index | YES | Cost paragraph tightened |

**Pass-2 verdict quoted:** "All fixes are statable inside rev-2's stop conditions — no new payload
field, no DDL, no index, no vocabulary — so a rev-3 applying F-A/F-B/F-C/F-D/F-E should ratify."
**Also surviving pass 2:** the release-exclusive boundary itself, the incremental debit, the scaling
disclosure, the wedge/normal sequence rule (the epoch-1 collision hypothesis was **disproven** — fold
and row both advance, so no normal release can reuse a consumed sequence), and parent D-R6a-5's
two-openers pin.

## §M4b record — pass 1 (10 findings: 1 P0, 3 P1, 5 P2, 1 P3) — retained, one row amended

As recorded in rev-2, unchanged except: **F-7 is WITHDRAWN** (pass-2 F-G — the claim was false at
`b48235e` and the planning seat's `Verified: YES` was not a verification). The remaining nine rows stand.
