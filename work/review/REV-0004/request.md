---
type: Review Request
rev_id: REV-0004
campaign_id: CAMPAIGN-0001
packet: ATTACK-CHAIN
container_group: spans G-A…G-I
packet_lens: adversarial red-team (primary) + cross-container end-to-end tracing (secondary)
status: AWAITING_REVIEW
targets: [chain-event-truth-claim, chain-submitted-not-filled, chain-kill-switch, chain-timeout-quarantine, chain-overfill-quarantine, chain-single-writer, chain-manual-flatten-deferral, chain-actor-audit]
human_gated_surfaces: [order-submission, cancel-replace, kill-switch, manual-flatten, live-shadow-config, event-log-truth]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: ["safety-core #8", "safety-core #9", "safety-core #10", INV-001, INV-002, INV-003, INV-020, INV-021, INV-022, INV-023, INV-024, INV-034, INV-036, INV-037, INV-050, INV-051, INV-052, INV-060, INV-075, "spine INV-1..9"]
adr_in_scope: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-008]
created: 2026-07-10
---

# Review Request REV-0004 — Attack-chain (cross-container adversarial red-team)

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you do
not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code, don't
rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md` first
(shared context; it makes **no** correctness claims — code beats the atlas, and if they disagree that
is itself a finding, ≥ P1). You have the full repo at the frozen SHA.

This packet is unlike the single-container packets. Its **unit of review is the chain, not a file
set** — each safety invariant traced end-to-end across every layer it touches (UI intent → `app.api`
→ `app.facade` → `app.<engine>` → `app.store` → `app.events` → back to the read model). Your job is
the defect that **only appears in the composition of correct-looking parts**: no single-container
reviewer sees it because each piece, read alone, looks right. This is explicitly **the packet that
would have caught REV-0001 F-001** — a double-submit that lived in the seam between the event-truth
read-flip and the submission claim gate, invisible to any store-only or engine-only review. Hunt
composition bugs.

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** Your "container" is the set of
safety-critical **chains** below; you must probe each one **exhaustively along its whole length**, and
your verdict covers whether those chains are composition-safe end-to-end. But you have the full repo
and are **encouraged to follow the bug anywhere** — see the Atlas "Your scope — follow the bug
anywhere". A defect you find in any file, in any container-group, is still your finding; report it
with its true `file:line` location and the synthesis will route it.

Two stances this packet leans on hardest (both from the Atlas):
- **Do not assume a neighbor's contract holds.** A chain is a sequence of hand-offs. If link N relies
  on a guarantee that link N−1 does not actually make, that reliance is **your** finding — re-derive
  the depended-on behavior from N−1's own code; do not take its docstring, its pinning test, or this
  packet's pointer on faith.
- **The bug lives in the seam.** The most valuable findings here are not "module X is wrong" but
  "module X and module Y are each internally consistent yet disagree at the boundary" (a read-model
  that folds one way while a writer gates on another; an actor threaded through four layers and
  dropped at the fifth; a lock released between a check and the act on it).

The other Wave-1 packets own the *depth* audit of individual containers (REV-0005 ENGINE, REV-0006
STORE-SPEC, REV-0007 EVENTS, REV-0008 ARCH). **Overlap with them is signal, not waste** — two
reviewers landing on the same defect from different directions is corroboration the synthesis treats
as higher confidence. Never stay silent to avoid duplication.

## What you're reviewing
The safety-critical execution chain, end to end: an operator (or the strategy loop) forms an intent;
it crosses the API boundary; the facade turns it into a command; the single-writer engine
(`app/monitoring.py`) drives **submit → poll → reconcile → protect → flatten**; the store
(`app/store/{core,memory,sqlite}.py`) applies it atomically under one lock and appends the durable
`ExecutionEvent`; the projectors (`app/events/projectors.py`) fold that log back into the order-status
and position read-models the next intent reads. **Every safety invariant in this repo is a property of
that whole loop, not of any one stop on it.** A single-writer engine cannot protect an invariant if
the read-model it gates on is folded from a stale column; a quarantine cannot hold if any one of four
entry paths re-drives the order; a kill switch cannot block intent if the block sits at a layer the
intent can route around.

For context, read the modules at `b600101` (the working tree is byte-identical to `b600101` for all
`app/` source — only governance files differ). There is no single diff to run; the whole spine is in
scope. The prior findings that motivate this packet — `work/review/REV-0001/result.md` (F-001/F-002,
the event-truth-vs-claim-gate class) and `work/review/REV-0002/result.md` (F-001 deferral masquerade,
F-002 dropped actor) — are worth reading as **calibration of the bug class**, not as answers (they are
reportedly addressed at this SHA; independently confirm the fixes hold and did not move the defect
elsewhere).

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Each pointer pairs a **stable symbol name** with its line at `b600101` so it re-locates if lines
drift. These say **where to enter a chain**, never what you'll find there.

**Chain 1 — Event-truth read-flip ↔ submission claim gate (the REV-0001 F-001 class; ADR-004,
INV-021, single-writer).**
- The read-flip: `project_order_status` (`app/events/projectors.py:278`) folds an order's lifecycle
  events to a status; `_project_order_unlocked` (`app/store/memory.py:1471`, folding at `:1486`) and
  `_project_order_locked` (`app/store/sqlite.py:2351`) are what `get_order` (`app/store/memory.py:1491`)
  and `list_orders` return.
- The gate: `claim_order_for_submission` (`app/store/memory.py:1212`; `app/store/sqlite.py:1975`).
  Both now derive the order from the projection **under the same lock** (memory `:1223`; sqlite `:1983`)
  before deciding, and both carry a co-write assertion (memory `:1231`; sqlite `:1989`) that fires if a
  raw column past `CREATED` still projects `CREATED`. The pure decision is
  `plan_claim_order_for_submission` (`app/store/core.py:1322`).
- Trace: is there **any** status-dependent write path (claim, transition, flatten supersede, backfill,
  reconcile-resolve) that still reads a raw `orders.status` column/object instead of the folded log
  under its lock? That is the exact shape of F-001.

**Chain 2 — Submitted ≠ filled / only fills move quantity (safety-core #8/#9, INV-001, spine
INV-1/INV-9).**
- Position derives **only** by folding FILL events: `project_symbol_position`
  (`app/events/projectors.py:117`), which calls `apply_fill(..., allow_short=True)` at `:137`.
- The engine never writes quantity — it appends fills: `store.append_fill` from the reconcile poll
  (`app/monitoring.py:1501`) and from inferred fills (`_apply_inferred_fills`, `app/monitoring.py:1803`,
  appending at `:1815`); the module header states the "position moved only by append_fill" contract at
  `app/monitoring.py:16`.
- The store fill path: `append_fill` (`app/store/memory.py:1655`; `app/store/sqlite.py:2583`) routes
  the decision through `plan_append_fill` (`app/store/core.py:212`) and co-writes the FILL event via
  `execution_event_for_fill` (`app/store/core.py:159`).
- Trace: can a `SUBMITTED`/`ACCEPTED` ack, a status transition, or a reconciliation ever move a
  position quantity without a deduped FILL event in the log (spine INV-9)?

**Chain 3 — Kill switch blocks new order intent (safety-core #10, INV-060, INV-021).**
- Entry: `POST /kill-switch` (`app/api/routes_controls.py:33`) → `set_kill_switch`
  (`app/facade/store_backed.py:909`).
- The block is at the **claim gate**, not at intent creation: `plan_claim_order_for_submission`
  (`app/store/core.py:1322`) applies the `HALTED`/buys-paused/session-closed re-check with the INV-060
  sell carve-out. Note the **deliberate asymmetry**: candidate creation is *not* gated —
  `run_strategy_tick` (`app/strategy_loop.py:103`) calls `store.create_candidate` (`:165`) and its
  header (`app/strategy_loop.py:26`) states buys are blocked at submission, not proposal.
- Protection tick's own kill read: `kill_switched = session.trading_state is TradingState.HALTED`
  (`app/monitoring.py:301`), consumed at `:310`; and in `cancel_open_buys` (`app/monitoring.py:221`).
- Trace: trip `HALTED` and follow **every** path that can reach `SUBMITTING` (strategy → candidate →
  order → claim; protection floor breach; manual flatten; emergency-reduce). Does any emit new BUY
  order intent past the gate?

**Chain 4 — Ambiguous/timeout → quarantine, never blind-resubmit (ADR-002, INV-023, spine INV-3).**
- The ambiguous-submit branch (`app/monitoring.py:703`, "next tick would blind-resubmit …") calls
  `store.quarantine_timed_out_order` at `:718`; the ambiguous **re-drive** branch (`:896`, "blind-
  re-driving an order that may now be live …") quarantines at `:906`.
- Resolution is a targeted **READ-ONLY** venue query: `_resolve_timeout_quarantine`
  (`app/monitoring.py:952`), driven from `run_monitoring_tick` (`:568`).
- Store side: `quarantine_timed_out_order` (`app/store/memory.py:1602`; `app/store/sqlite.py:2517`) via
  `plan_quarantine_timed_out_order` (`app/store/core.py:1938`).
- Reconcile keying: `plan_reconciliation` (`app/reconciliation.py:204`) matches broker reports to local
  orders by `client_order_id == order.id` (documented at `:219`; `by_client_id` built at `:224`, hit at
  `:246`), under `ReconcileQueryBudget` (`app/reconciliation.py:69`).
- Trace: from **every** origin (submit sweep, stale re-drive, `on_stream_reconnect` at
  `app/monitoring.py:502`, `run_startup_reconcile` at `:481`), can a quarantined order be re-submitted or
  re-driven before the read-only query resolves it?

**Chain 5 — Broker-authoritative overfill recorded + quarantined (ADR-001, spine INV-4, INV-002).**
- Decision: `plan_append_fill` computes `is_overfill = would_go_negative(...)`
  (`app/store/core.py:335`) and — per the comment at `:326-334` — RECORDS the fill + FILL event and
  quarantines rather than dropping it.
- Read side: `project_symbol_position` folds the recorded short (`allow_short=True`,
  `app/events/projectors.py:137`); `quarantined_symbols` (`app/events/projectors.py:141`) latches the
  symbol so autonomous BUY intent is blocked.
- Engine tolerance: `NegativePositionError` import (`app/monitoring.py:70`) and `_FILL_ERRORS`
  (`app/monitoring.py:113`).
- Trace: is the overfilled/negative fact recorded **and** quarantined **and** does autonomous trading
  halt for that symbol — across both stores and through replay?

**Chain 6 — Manual-flatten deferral: exit risk without double-exit or blind-cancel (ADR-003,
INV-034/036/037; the REV-0002 F-001 class).**
- Entry: `POST /positions/{symbol}/flatten` (`app/api/routes_trading.py:90`) → `create_exit`
  (`app/facade/store_backed.py:789`), which clears open buys via the facade→engine seam
  `from app.monitoring import cancel_open_buys` (`app/facade/store_backed.py:79`, called at `:815`),
  then calls `store.flatten_position` (`:818`) and surfaces a distinct deferral (`:826-836`).
- Emergency path: `POST /positions/{symbol}/emergency-reduce` (`app/api/routes_trading.py:115`) →
  `emergency_reduce_override` (`app/facade/store_backed.py:930`, authorize at `:953`, cancel buys at
  `:957`).
- Store + planner: `flatten_position` (`app/store/memory.py:928`; `app/store/sqlite.py:1624`) →
  `plan_flatten_position` (`app/store/core.py:982`): `HALTED` deny at `:1021`; the INV-036 live-protection
  deferral carve-out at `:1046` (predicate `active_order.status is not OrderStatus.CREATED`, `:1049`)
  emitting `MANUAL_FLATTEN_DEFERRED` with the actor at `:1051-1069`; the supersede/self-heal branch at
  `:1076`.
- Trace: over a `SUBMITTED` vs `CANCEL_PENDING` vs `TIMEOUT_QUARANTINE` protection order, does the
  operator get a truthful distinct outcome (never "flatten submitted" for a deferral), and is a live
  BUY never cancelled by the store itself (INV-037)?

**Chain 7 — Single-writer + atomicity under one lock (INV-050/051/052, safety-core single-writer).**
- The engine is the only writer; every store mutation is one atomic lock hold with the broker call
  *outside* it (INV-052). The facade→engine edge (`app/facade/store_backed.py:79`) and the flatten
  buy-cancel pre-step (`:815`) are the two places a broker round-trip and a store write meet — trace
  that no lock is held across the `await`.

**Chain 8 — Actor / audit provenance threaded end-to-end (observability; the REV-0002 F-002 class).**
- `get_actor` (`app/api/deps.py:77`, `DEFAULT_ACTOR = "operator"` at `:23`) → route (`actor` param at
  `app/api/routes_trading.py:94`, `:119`; `app/api/routes_controls.py:37`) → facade
  (`app/facade/store_backed.py:789`, `:909`, `:930`) → store → planner (`actor` into
  `plan_flatten_position`, `app/store/core.py:989`, stamped on the deferral event at `:1065`).
- Trace: does **every** state mutation co-emit its lifecycle + audit event with the actor threaded, or
  is there a mutation with no audit trail / a wrong-or-missing actor at any hand-off?

## Probe checklist (find the failing composition, or prove it cannot exist — symmetric challenges)
Each item is a **chain**, not a file. Construct the failing end-to-end interleaving with a runnable
repro, **or** prove the composition of the parts makes it impossible (and paste what you ran).

**CLUSTER A — Read-model ↔ writer seam (the F-001 class)**
1. Drive an order to log-`SUBMITTED`, then desynchronize the co-written `orders.status` column to a
   pre-submit value by any reachable path (backfill, a partial write, a reconcile-resolve). Find a
   status-dependent **write** path — claim, transition, flatten supersede, cancel — that acts on the raw
   column instead of the folded log and lets the order re-enter submit or regress its lifecycle. Show
   the interleaving in **both** stores, **or** prove every status-gated writer folds the log under its
   own lock before deciding (and that the co-write assertions at `memory.py:1231`/`sqlite.py:1989` are
   reachable tripwires, not dead code).
2. `project_order_status` folds **latest-lifecycle-event-wins by append sequence** and ignores
   `authority` (ADR-008, INV-075). Construct — or prove unreachable at `b600101` — any order-status
   ingest path that appends out of causal order or asserts a conflicting fact (reconcile-resolve, a
   stale engine echo after a broker fact) so latest-wins mis-projects a status the claim/cancel/flatten
   logic then gates on. INV-075 is a *forward-looking* tripwire; the finding is either "a path exists
   today" or "the tripwire is correctly the only thing standing between here and that path."

**CLUSTER B — Position truth (submitted ≠ filled)**
3. Find any composition where a position quantity moves without a deduped FILL event: a `SUBMITTED`
   ack that reaches the position read-model (spine INV-9), a status transition that writes quantity, a
   reconcile that infers a fill and a later real observation of the same execution that both land (INV-3
   dedup on `source_fill_id`), or a projector that folds a non-FILL event into quantity. Show it, **or**
   prove `project_symbol_position` + `plan_append_fill`'s dedup make it impossible across both stores.
4. A broker overfill drives a long position negative. Trace the full chain: is the fill **recorded**
   (not dropped), the symbol **quarantined** (`quarantined_symbols` latches it), autonomous BUY intent
   **blocked** at the claim gate, and does the negative survive **replay** identically in memory and
   sqlite? Find a link where the fact is hidden, rejected, or fails to halt trading — or prove ADR-001's
   record-and-quarantine holds end-to-end.

**CLUSTER C — Kill switch reaches every intent path**
5. Trip `HALTED` and, for **each** intent origin (strategy candidate → order → claim; protection floor
   breach; manual flatten; emergency-reduce), prove no new BUY order intent is emitted past the claim
   gate. Exploit the deliberate asymmetry — candidate creation is *ungated* (`strategy_loop.py`) —
   to find a path where an order created (or already `CREATED`) before/while `HALTED` still reaches
   `SUBMITTING`. Show the leak, or prove the single choke point (`plan_claim_order_for_submission`) is
   truly the only `CREATED → SUBMITTING` edge (INV-021) and that no path bypasses it.
6. Verify the INV-060 carve-out is exactly as narrow as stated: a `MANUAL_FLATTEN` sell bypasses all
   controls; a `PROTECTION_FLOOR` sell bypasses buys-paused/closed-session but **not** the kill switch;
   nothing else bypasses. Find a widening (a sell reason that bypasses more than its row allows, or a BUY
   that slips the gate), or prove the gate enumerates only those two exceptions.

**CLUSTER D — Ambiguity containment**
7. Force an ambiguous broker submit (per REV-0011's documented adapter timeout contract). Show the
   order lands in `TIMEOUT_QUARANTINE` and that **none** of {submit sweep, stale re-drive,
   `on_stream_reconnect`, `run_startup_reconcile`, reconcile plan} re-submits or re-drives it before
   `_resolve_timeout_quarantine`'s **read-only** query resolves it (ADR-002, spine INV-3). Find a path
   that escapes quarantine, **or** prove all four origins are blocked while quarantined — in both stores
   and across a simulated restart.
8. Race `ReconcileQueryBudget` accounting and the `by_client_id` keying: can a report matched by
   `client_order_id` be mis-attributed, or the budget over-spent, under out-of-order/concurrent calls,
   so an inferred fill or resolution lands on the wrong order? Show it or prove the keying + budget are
   race-safe.

**CLUSTER E — Manual flatten (the deferral masquerade class)**
9. For a protection order at `SUBMITTED`, then `CANCEL_PENDING`, then `TIMEOUT_QUARANTINE`, drive the
   full route→facade→store→planner→response chain and confirm the operator is told the **distinct**
   truth ("already exiting / no manual order submitted") and never "flatten submitted", and that the
   store **never** blind-cancels a possibly-live protection order (ADR-002) nor double-exits (INV-036).
   Find a status where the deferral still masquerades as a submitted exit (the REV-0002 F-001 shape) or a
   status where a live protective order is double-exited — or prove the `:1046-1049` predicate + the
   `:826-836` response surfacing are truthful for every non-`CREATED` status.
10. Prove `flatten_position` never itself cancels a live BUY (INV-037) — the cancel is the route/facade
    pre-step (`cancel_open_buys`, outside the lock) — and that `flatten_position` re-reads the live
    position under its own lock so a buy filling concurrently with the cancel is still sized correctly.
    Find a window where the store holds its lock across the broker cancel (INV-052), or where a partial
    buy fill during the cancel mis-sizes the exit.

**CLUSTER F — Single-writer, atomicity, actor**
11. Audit every place a broker call and a store write meet (`create_exit`'s cancel→flatten,
    `emergency_reduce_override`, the submit path): is any store lock held across an `await` to the broker
    (INV-052)? Is any invariant checked before an `await` and acted on after with no re-check (a TOCTOU)?
    Is task cancellation on shutdown safe mid-write (no partial mutation, INV-050)? Show a violation or
    prove the lock/await discipline holds.
12. Trace the actor from `get_actor` through route → facade → store → event payload for **every**
    human-gated mutation (flatten create, flatten defer, emergency-reduce, kill switch, cancel). Find a
    mutation whose audit event drops or defaults the actor when a real one was available (the REV-0002
    F-002 shape), or an actor-less state change — or prove the thread is unbroken. (Note the disclosed
    "actor is always `operator`" reality — the header is never sent — and decide whether that is a
    finding at this severity or an accepted beta limitation.)

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Probe the **code** against the invariant **statements**, never against the pinning tests. Per the
X-002 rule (`ATLAS.md`, `docs/INVARIANTS.md` preamble), a test can assert the very bug it should catch
— "pinned by" is provenance, not proof. Your oracles for this packet:
- **`docs/INVARIANTS.md`** — INV-001/002/003 (position/fills), INV-020..024 (order lifecycle), INV-034/
  036/037 (flatten), INV-050/051/052 (atomicity/lock), INV-060 (kill-switch carve-out), INV-075 (order-
  status ordering tripwire). Re-derive "what must always hold" from the statement text and probe the
  chain directly.
- **`CLAUDE.md` safety core** — #8 submitted≠filled, #9 only fills change qty, #10 kill switch blocks
  intent, single-writer, "the UI never calls Alpaca", "submitted does not equal filled."
- **`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`** — spine `INV-1..9` (note: a **separate** numbering
  from the INV-0xx registry — see the Atlas ID-collision note). INV-1 (fills only), INV-3 (block on
  ambiguity), INV-4 (no oversell pre-submit *and* post-fill), INV-9 (acks never reach the Position
  Service) are the load-bearing ones for these chains.
- **ADRs** — ADR-001 (overfill quarantine), ADR-002 (timeout quarantine / no blind redrive), ADR-003
  (manual flatten under Halted/Reducing), ADR-004 (event-log-as-truth), ADR-005 (facade is the only
  route→backend seam), ADR-008 (order-status provenance + the latest-wins truth model).

If the code contradicts the Atlas, a disclosed known-item, or an ADR's stated contract, **that
disagreement is itself a finding** (≥ P1) — the map, not just the code, may be wrong.

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** — a probe script, a `pytest -k`, or a shell
  command — **plus its pasted output**, exercised **dual-store** (memory + sqlite) wherever the chain
  touches the store, and through **replay** (`app/events/replay.py`) where the claim is about durable
  truth. A finding with no repro is marked **"unverified concern"** and **cannot gate**.
- Because this is a chain packet, a repro should drive the **real functions across the seam** (the
  monitoring-loop functions, the facade methods, the store methods) — not just a planner in isolation —
  so the composition bug actually manifests. A pure-planner probe that can't reach the read-model is
  weaker evidence here than in a single-container packet.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran**. A bare "looks
  fine / LGTM" with no probe log is a **rejected review** for that chain — show your work on clean code
  too. Null results are first-class output here: "I drove the F-001 desync against all four
  status-gated writers in both stores and the log-fold held; here is the script and its output" is
  exactly the coverage this packet exists to produce.
- State plainly anything you could **not** verify (e.g. real-broker timing you cannot exercise; a race
  you can only argue structurally). Environment-dependent results must be labeled (Python 3.12 per the
  Atlas — a prior round produced spurious 3.14 SQLite `ResourceWarning` failures).

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0004/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and — because this
packet is the cross-container gate — a plain statement of **whether the safety spine is composition-
solid end-to-end** (are chains 1–8 defect-free across the seams, or which chain blocks). Report any
defect at its **true `file:line`**, even when it lives in another packet's container. Do **not** edit
`request.md`; do **not** push code fixes.
