---
type: Planning Disposition
title: "Signal Seat R5b-1 — disposition of the five NEEDS-INPUT blockers"
status: RATIFIED-PENDING-OPERATOR
author: planning seat
created: 2026-07-25
branch_under_disposition: "codex/signal-r5b1-producer-ingest @ 5402ed7 (local only)"
---

# R5b-1 NEEDS-INPUT — planning-seat disposition

Codex stopped before RED with five blockers. **All five verified independently against the staging
corpus and accepted spec text before disposition. All five are real, and two are defects in WO-0138
itself.** Stopping was correct — B5 touches event-log truth, which CLAUDE.md requires be escalated,
not coded around.

**Root cause of three of the five:** WO-0138 deferred `GET /api/signals` to R5b-2 (rev-2 OUT list)
but kept `tests/test_signal_facade_reads.py` — the read-side corpus — in R5b-1's IN list. That corpus
is *entirely* lazy-expiry/effective-status/injected-clock work, and it depends on
`effective_signal_status`, which **WO-0139 D-R5b2-16 already assigns to R5b-2**. The read half was
split across two rungs. This disposition reunites it.

---

## D1 — `received_at` omitted at 8 sites, not the authorized 6 → **MOOT for R5b-1 (corpus moves)**

**Verified:** `tests/test_signal_facade_reads.py` contains **11** `ingest_signal(` calls and only 6
`received_at` mentions. WO-0138 D-R5b1-2 authorized 6 repairs on M4b's count. Codex's live count of 8
is the accurate one.

**Disposition:** the entire facade-read corpus moves to R5b-2 (D5 below), so this repair moves with
it. When R5b-2 imports it, the authorized mechanical repair is **"every `ingest_signal(` call site
missing the required `received_at=` kwarg"** — a *predicate*, not a count. Counting was the error;
WO-0139 must not repeat it.

## D2 — three ingest tests depend on the deferred `GET /api/signals` → **RESOLVED by re-scope**

**Verified:** `tests/test_signal_routes.py:231`
(`assert client.get("/api/signals", headers=_OP_H).json() == []`) sits inside the ingest subset and
needs both the deferred GET route and operator-key auth. Lines `284-286` and `320` are operator-matrix
tests already assigned to R5b-2. Line `65` (`.get("/api/signals") == 404`) is a **flag-off** assertion
and is fine either way — an unmounted route 404s regardless.

**Disposition:** any ingest test that reads back through `GET /api/signals` **moves to R5b-2** with the
route. R5b-1 imports only ingest cases whose assertions terminate at the **HTTP response + the event
log**, never at a read-back route. Do not rewrite an assertion to avoid the GET — moving it is correct;
rewriting it would be test-weakening.

## D3 — producer-auth coverage entangles operator-key behavior → **AUTHORIZED, narrowly**

**Verified:** `_OP_H = {"X-Operator-Key": OPERATOR_KEY}` (`:34`) and the producer-route negative
asserts an operator key on `POST /api/signals` ⇒ **403** (wrong role), distinct from 401. That is part
of the **producer route's own** authorization contract (spec `04 §1`: "a producer key on an operator
route (or vice versa) is a 403, distinct from 401"), not operator *enforcement*.

**Disposition — bounded authorization:** R5b-1 **may** recognize the operator credential as a distinct
credential type **solely to return 403 on `POST /api/signals`**. It must **not** enforce the operator
key on any other route, add operator middleware, or stamp a principal — all still R5b-2. Any staged
assertion about operator behavior on a *non-producer* route moves to R5b-2.

## D4 — `SignalProposal` must live in `app/api/schemas.py`, outside the IN list → **WO-0138 DEFECT; authorized**

**Verified:** `docs/spec/signal-seat/01-schema.md:6` — "`SignalProposal` … **Pydantic model in
`app/api/schemas.py`**". WO-0138's IN list omitted that path, so the contract as written could not
produce a working route. **This is a defect in my work order, not an implementer scope question.**

**Disposition:** `app/api/schemas.py` is **added to R5b-1's allowed paths**, scoped to **adding signal
DTOs only** (`SignalProposal` plus any ingest response view). No edits to existing schemas; the
existing `ResponseSafeFloat` conventions apply.

## D5 — lazy reads and `SIGNAL_EXPIRED`: an accepted-text conflict on event-log truth → **ESCALATED**

**Verified — the conflict is real and squarely on a safety surface.** Accepted
`docs/spec/signal-seat/02-lifecycle.md:47` defines `SIGNAL_EXPIRED` as emitted by "sweep,
**lazy-expiry**, or dead-on-arrival at ingest", with a required payload field
`detected_by: "sweep" | "read" | "ingest"` — **`"read"` is an accepted enum value** — and `:97` says
"TTL lapse … EXPIRED (**lazy** + sweep, rule A4)". The staged corpus asserts the opposite:
`test_list_signals_lazy_expiry_does_not_mutate_store` (`:112`), alongside
`test_get_signal_lazily_expires_stale_received` (`:69`) and
`test_facade_injected_clock_makes_expiry_boundary_deterministic` (`:205`).

So: does a read that observes a lapsed TTL **append a durable `SIGNAL_EXPIRED` event**, or merely
**reclassify in the projection**? This is beyond the authorized 413 amendment and is not the
implementer's call.

**Planning-seat recommendation — mutation-free reads, with a spec amendment.** Reads reclassify via a
pure `effective_signal_status(record, now)`; the **durable** `SIGNAL_EXPIRED` is written by the sweep,
at ingest (dead-on-arrival), or atomically inside the A-2 conversion command. Rationale:

1. **Single-writer discipline.** A producer-facing GET that appends to the event log makes the API read
   path a writer. The spine's architecture reserves mutation for the engine; a read-triggered append
   crosses that seam.
2. **Write amplification on a hostile-input surface.** Reads that write turn a read burst into an event
   burst — precisely the paced-hostility class R6's rails exist to bound.
3. **`effective_signal_status` already exists as the mechanism** (WO-0139 D-R5b2-16) — derivation is the
   designed path.
4. **Rule A3 is preserved either way:** a stale signal can never be approved, because conversion
   re-checks TTL atomically (A-2/A-3) regardless of whether a read wrote an event.
5. The staged corpus already pins mutation-free reads, so the *tests* and the *spec* disagree — and
   under the CLAUDE.md conflict rule the accepted spec normally wins, which is exactly why this needs a
   **deliberate amendment** rather than a silent choice.

**Required if accepted:** amend `02-lifecycle.md` to state that lazy expiry is **projection-level
reclassification** and to remove `"read"` from `detected_by` (or redefine it as sweep-attributed).
This is an **event-log-truth change on a human-gated surface** ⇒ operator ratification **plus** its own
review packet before any rung relies on it.

**Interim disposition (unblocks R5b-1 today):** the whole question travels with the facade-read corpus
to **R5b-2**, which owns `effective_signal_status`. **R5b-1 does not implement lazy expiry at all.**
Ingest-time dead-on-arrival (`expires_at ≤ received_at` ⇒ `SIGNAL_EXPIRED` with `detected_by:"ingest"`)
is unaffected and stays in R5b-1 — it is a write on the write path, not a read.

---

## Net effect: R5b-1 re-scoped to ingest-only

**IN (R5b-1):** `SignalProposal` + ingest DTOs in `app/api/schemas.py` (D4) · the typed signal facade's
**write/ingest** surface · `POST /api/signals` (body-blind, 64 KiB → 413, manual validation) ·
producer-key auth + server-side identity binding · the wrong-role **403 on the producer route only**
(D3) · ingest-time dead-on-arrival expiry · `.importlinter` contract 5 · the ingest subset of
`test_signal_routes.py` whose assertions terminate at the HTTP response or the event log.

**MOVED to R5b-2 (WO-0139):** the entire `tests/test_signal_facade_reads.py` corpus · facade
`list_signals`/`get_signal` · `effective_signal_status` · the injected read clock · lazy-expiry
semantics and the D5 decision · any ingest test that reads back via `GET /api/signals`.

This makes R5b-1 genuinely additive and tight, and it consolidates **all** read-side work in the rung
that already owns `GET /api/signals`.

## WO amendments required (planning seat, before resume)

1. **WO-0138:** add `app/api/schemas.py` (signal DTOs only) to allowed paths; move
   `test_signal_facade_reads.py` and the read-side facade methods to the OUT list; restate the
   `received_at` repair as a **predicate**, not a count; record the D3 bounded authorization.
2. **WO-0139:** add the facade-read corpus, `list_signals`/`get_signal`, the injected clock, the
   `received_at` predicate repair, and **the D5 decision** to its scope; note that D5 must be
   ratified before those tests can go green.
3. **Ledger/plan:** no round-count change — R5b-1 and R5b-2 both keep their slots.
