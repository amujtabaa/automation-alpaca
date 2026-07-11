---
type: Review Request
rev_id: REV-0007
campaign_id: CAMPAIGN-0001
packet: EVENTS
container_group: G-D (event sourcing)
packet_lens: data-integrity (primary) + adversarial red-team (secondary)
status: AWAITING_REVIEW
targets: [G-D-events]
human_gated_surfaces: [event-log-truth]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #8, safety-core #9, INV-001, INV-002, INV-003, INV-004, INV-050, INV-051, INV-075, "spine INV-1", "spine INV-9"]
adr_in_scope: [ADR-004, ADR-008, ADR-001, ADR-002, ADR-003]   # ADR-004 + ADR-008 are the PRIMARY oracles; ADR-001/002/003 are in scope because the quarantine / timeout-quarantine / emergency-override projectors here literally implement their read models
created: 2026-07-10
---

# Review Request REV-0007 — Event sourcing (projectors + replay/parity), data-integrity

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes no correctness claims — code beats the atlas, and if they
disagree that is itself a finding). You have the full repo at the frozen SHA.

This packet's lens is **data-integrity first**: in G-D the **fold IS the source of truth**.
`orders.status`, `sessions.trading_state`, and the position/quarantine columns are all co-written
**read models** whose first durable write is an `ExecutionEvent` and whose value must be
reconstructable by replaying the log (ADR-004). So the question is not "does the UI show the right
number" — it is "does folding the append-only log **deterministically and totally** yield the one
correct read model, and does it yield the **same** model from either store." The **red-team** lens
is secondary: can a crafted event sequence fold to a wrong terminal status, resurrect a terminal
order, double-count a fill, or split memory from sqlite.

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/events/projectors.py` (~473 LOC) — the pure fold functions: order-status projection,
  position projection, the overfill / timeout / emergency-override quarantine sets, the
  per-session TradingState composition, and the two frozensets that define the status vocabulary.
- `app/events/replay.py` (~248 LOC) — the replay + dual-store parity mechanism that is supposed to
  *prove* both stores fold identically and that snapshot+resume equals a from-scratch replay.

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds**.
The projectors here are pure functions over a `list[ExecutionEvent]` they do **not** produce; every
correctness claim below is conditional on *how the store feeds them events*. **If a projector is
only correct under an assumption about the event stream (ordering, dedup, terminality, which
event types can appear), re-derive that assumption from the feeding module's code and report the
reliance as YOUR finding** — do not take the projector's docstring or this request on faith.
- the store impls that call these projectors and own `get_execution_events` ordering / append-time
  dedup → REV-0009 (STORE-IMPL) and REV-0006 (STORE-SPEC).
- the single-writer engine that decides *what* events get appended and in what causal order →
  REV-0005 (ENGINE).
- `app/models.py` (event schema), `app/position.py::apply_fill`, `app/policy.py` predicates →
  REV-0010 (KERNEL).

## What you're reviewing
`projectors.py` folds the append-only `ExecutionEvent` log into read models. The safety-critical
ones: `project_order_status` derives an order's `status` by **latest-lifecycle-event-wins over
append sequence**, treating `source`/`authority` as **provenance-only** (never a resolution input
— ADR-008 "Truth model"); `PositionProjector` / `project_symbol_position` derive position by
folding **FILL** events through `apply_fill`; `quarantined_symbols` / `timeout_quarantined_order_ids`
/ `active_emergency_reduce_overrides` / `current_trading_state` fold the other event-truth sets.
`replay.py` is the enforcement mechanism: `verify_dual_store_parity` and
`verify_dual_store_readmodel_parity` replay both stores' logs and assert the projections match, and
`verify_snapshot_replay` asserts `project(all) == resume(snapshot@k, all)`.

Run for context: `git diff b600101~1..b600101 -- app/events/projectors.py app/events/replay.py`
(or just read both files at `b600101`).

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Line numbers are paired with a stable symbol so they re-locate if the file drifts. These are
**neutral entry points**, not claims about what you'll find.

- **Order-status fold** — `project_order_status` (`app/events/projectors.py:278`); its per-event
  loop (`:297-308`) with the `event.order_id != order_id` filter (`:298`), the `FILL` branch that
  accumulates `filled` (`:300-302`), and the lifecycle-status assignment via
  `_LIFECYCLE_EVENT_TO_STATUS.get(...)` (`:303-304`). The status→event map is
  `_LIFECYCLE_EVENT_TO_STATUS` (`:246`) and its public projection is the `ORDER_STATUS_EVENT_TYPES`
  frozenset (`:264`). The `min(filled, quantity)` cap is at `:306-307`.
- **The status vocabulary vs the enum** — `ExecutionEventType` (`app/models.py:346`) declares the
  full event vocabulary; compare its members against the keys of `_LIFECYCLE_EVENT_TO_STATUS`
  (`:246-256`). Note which enum members are and are not mapped.
- **The legal-transition graph** — `ORDER_TRANSITIONS` (`app/transitions.py:45`). ADR-008's
  "Truth model" describes the fold as latest-wins "bounded by the legal-transition graph." Locate
  where (or whether) `project_order_status` consults this table.
- **Position fold** — `PositionProjector.project` / `.resume` / `._apply`
  (`app/events/projectors.py:425` / `:431` / `:453`), `project_symbol_position` (`:117`), and
  the single fold step `_fill_from_event` (`:66`), which validates a FILL event via the shared
  `fill_value_reason` predicate (`app/policy.py:233`) and applies it through
  `apply_fill` (`app/position.py:37`) with `allow_short=True` (`:137`, `:472`).
- **Fill idempotency surface** — `apply_fill` (`app/position.py:37`) and the FILL-consuming loops
  in `project_symbol_position` (`:129-137`), `quarantined_symbols` (`:177-183`),
  `PositionProjector._apply` (`:459-472`), and the `filled` sum in `project_order_status`
  (`:300-302`). Observe what each does with the event's `dedupe_key` / `source_fill_id`.
- **Quarantine / state folds** — `quarantined_symbols` (`:141`, latched-crossing comment at
  `:150-166`), `timeout_quarantined_order_ids` (`:202`) over `_ORDER_LIFECYCLE_EVENT_TYPES`
  (`:191`), `active_emergency_reduce_overrides` (`:394`), and the TradingState composition path
  `_driver_trading_state` (`:332`) → `control_trading_state`/`reconcile_trading_state`
  (`:353`/`:362`) → `current_trading_state` (`:372`) → `compose_trading_state` (`:321`).
- **The ordering precondition** — the module docstring's precondition ("events must be supplied in
  ascending `sequence` order … projectors do not re-sort," `app/events/projectors.py:14-18`) and
  the store side that is supposed to satisfy it: `get_execution_events`
  (`app/store/sqlite.py:2869`, whose query `SELECT * FROM execution_events WHERE sequence > ?
  ORDER BY sequence` is at `:2878`; the per-order variant `ORDER BY sequence` is at `:2363`) and
  `app/store/memory.py:1849`.
- **Replay / parity** — `verify_dual_store_parity` (`app/events/replay.py:108`),
  `verify_dual_store_readmodel_parity` (`:236`) and its `project_read_models` (`:166`),
  `verify_snapshot_replay` (`:78`), `compare_projections` (`:67`). Read the scope note at
  `:121-141` describing what the parity verifier does and does **not** cover.
- **Pinning tests (context only — see the X-002 hook below):**
  `tests/test_wo0007b_stageb_projector.py` (order-status fold),
  `tests/test_wo0007a_quarantine_consumer_unaffected.py` (timeout set),
  and the replay/parity suites. Read them to understand intent; **do not adopt them as the oracle.**

## Probe checklist (find the failure, or prove it cannot exist — symmetric challenges)
Each probe is a symmetric challenge: **construct the event sequence that folds wrong, OR prove the
fold is invariant to it.** Both directions are valid results; a proof needs the same rigor as a
repro. Probes are grouped by cluster.

**DATA-INTEGRITY / fold-determinism**
1. **Ordering key.** The docstring says the fold is by ascending `sequence` but the loops iterate
   the supplied list in iteration order and do not re-sort. Construct an input list whose iteration
   order disagrees with `event.sequence` (e.g. a later-sequence event earlier in the list) and show
   whether `project_order_status` / `timeout_quarantined_order_ids` / `_driver_trading_state`
   fold to a **different** status/state than the sequence order would give — **or** prove the fold
   is sequence-ordered regardless of list order. Then follow the reliance: re-derive from the store
   whether `get_execution_events` (both impls) actually guarantees ascending, gap-free, unique
   `sequence` under normal and concurrent append, and report any gap as your finding.
2. **Totality.** Enumerate every `ExecutionEventType` member (`app/models.py:346`). For each,
   determine whether the status fold maps it, skips it, or drops it silently, and whether that is
   correct per the transition graph and ADR-004. Find an event type that *should* move a read model
   but is silently ignored (or one that is mapped but shouldn't be), **or** demonstrate the mapping
   is total and every unmapped type is correctly inert.
3. **Malformed-event symmetry.** `_fill_from_event` raises `ProjectionError` on a FILL missing
   `symbol`/`side`/`quantity`/`price` or with a value `fill_value_reason` rejects; but the `filled`
   sum in `project_order_status` reads `event.quantity or 0` without that guard. Construct a single
   malformed FILL event and show whether the position fold and the status fold treat it
   **consistently** (both reject) or divergently (one raises, one silently folds a wrong number) —
   **or** prove no reachable event can trigger the asymmetry.
4. **Snapshot/resume equivalence.** `verify_snapshot_replay` asserts `project(all) ==
   resume(snapshot@k, all)`. `resume` filters `e.sequence > snapshot.up_to_sequence` while `_apply`
   advances `up_to_sequence` to the max sequence seen. Construct an event stream (duplicate
   sequences, out-of-order tail, a snapshot taken mid-run) where the equivalence **fails**, or prove
   it holds for any split `k`.

**DEDUP / idempotency**
5. **Replayed fill does not move quantity twice (safety-core #9, INV-001, INV-003).** None of the
   FILL-consuming folds call a dedup step; `apply_fill` applies unconditionally. Construct a log
   containing two FILL events for one order that represent the **same** broker fill (same
   `dedupe_key`/`source_fill_id`) and show whether `PositionProjector`, `project_symbol_position`,
   `quarantined_symbols`, and the `filled_quantity` sum each **double-count** it — **or** re-derive
   from the store (append-time dedup) and the spec that the event log structurally cannot contain
   two FILL events with the same dedupe key, and report the projector's reliance on that guarantee
   as your finding either way.
6. **filled_quantity truth (INV-004).** `project_order_status`'s `filled_quantity` is a raw Σ of
   FILL quantities capped at `quantity`. Show whether a duplicate or partial-then-full fill sequence
   can make the projected `filled_quantity` disagree with the sum of *distinct* recorded fills (the
   cap masks some over-counts but not all) — or prove it always equals the deduped sum.

**PROVENANCE / INV-075 authority-leak**
7. **The fold must not read provenance (ADR-008 "Truth model", INV-075).** Prove, by reading every
   branch of `project_order_status` (and the other status/quarantine/state folds), whether any path
   reads `event.source` or `event.authority` to decide a status/quarantine/state outcome — or find
   the path that does (that is the INV-075 tripwire and a P0-class finding). Then the harder half:
   construct a **crafted-but-append-legal** sequence where a later-sequence `LOCAL`/engine event
   supersedes an earlier `BROKER_AUTHORITATIVE` fact (or vice-versa) and yields a wrong read model,
   and re-derive from the engine/store whether such an ordering is reachable today — the INV-075
   statement is explicitly a *forward tripwire*, so "unreachable today, but this path would break
   it" is a valid and wanted result.
8. **Transition-graph bounding.** ADR-008 says the fold is latest-wins **bounded by the
   legal-transition graph** (`ORDER_TRANSITIONS`). Determine whether `project_order_status`
   enforces that bound itself or relies on the writer to only ever append legal transitions.
   Construct a sequence containing an illegal edge (or a post-terminal event) and show what the fold
   returns; re-derive who — if anyone — guarantees the input never contains it.

**RED-TEAM / parity**
9. **Resurrect a terminal order.** `CANCELED`/`REJECTED`/`FILLED` are terminal in the transition
   graph, but latest-wins has no terminality guard. Construct `[…, CANCELED, SUBMITTED]` (or
   `[…, FILLED, CANCEL_PENDING]`) for one order and show the fold **resurrects** it to a non-terminal
   status — then re-derive whether the single-writer engine can ever append a post-terminal
   lifecycle event, and report the reliance. Symmetric: prove terminal states are structurally
   unreachable-to-supersede if that is what the writers guarantee.
10. **Parity break.** Construct (or argue for) a scenario where the memory and sqlite logs fold to
    **different** read models — divergent event ordering, a dedup that fires in one store but not the
    other, or an event present in one log and not the other — and show whether
    `verify_dual_store_parity` / `verify_dual_store_readmodel_parity` would **catch** it. Then check
    coverage: the parity verifier's own scope note (`app/events/replay.py:121-141`) states the
    order-status/spawn projection is **not** covered by the replay parity check. Confirm whether
    `project_order_status`'s read model is parity-checked by *any* runnable mechanism here, or only
    by pinning tests — a co-written read-model column that no replay verifier reconstructs is a
    reconstructability gap under ADR-004's "Required tests."

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the **code** against the invariant **statements** in `docs/INVARIANTS.md` and the **ADR text**,
never against the pinning tests. Per the X-002 rule (ATLAS "The X-002 rule"), a test can assert the
very bug it should catch. In particular:
- `tests/test_wo0007b_stageb_projector.py` **pins** the order-status fold — including a comment that
  an out-of-legal-order `[FILLED@1, CANCEL_PENDING@2]` sequence is "unreachable in production" and
  a "(+ the legal-transition graph)" annotation. **Do not treat that test, or its comments, as the
  oracle.** Derive "what must always hold" from **INV-075** (`docs/INVARIANTS.md`) and **ADR-008
  "Truth model (this flow)"**, and probe the code directly.
- Position/fill truth: **safety-core #8** (submitted ≠ filled), **safety-core #9 / INV-001**
  (only fills change quantity), **INV-002** (never silently short), **INV-003** (duplicate fill
  never double-counts), **INV-004** (`filled_quantity` = Σ recorded fills), and **spine INV-1 / INV-9**
  (`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`).
- Quarantine / override read models: **ADR-001** (overfill quarantine — `quarantined_symbols`),
  **ADR-002** (timeout quarantine — `timeout_quarantined_order_ids`), **ADR-003** (emergency-reduce
  override — `active_emergency_reduce_overrides`).
- Reconstructability / dual-store parity: **ADR-004 "Required tests"** ("in-memory and SQLite event
  logs/projections match"; "snapshot-plus-replay equals full replay") is the parity **property**
  oracle; **INV-050 / INV-051** are the store-side atomicity/lock underpinnings the ATLAS glossary
  ("Dual-store parity") ties parity to. (Transparency: the registry has **no** standalone "INV-parity"
  number — parity is anchored in ADR-004's required-tests list plus INV-050/051, per the campaign's
  own glossary convention. If you think the parity property deserves its own registry entry, that
  observation is itself a finding.)

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** (a probe script, a `pytest -k`, or a Python
  snippet building `ExecutionEvent`s and calling the projector) **plus its pasted output**. Where a
  finding is about parity or the store's feed, exercise it **dual-store** — memory **and** sqlite —
  through the actual mechanism (`verify_dual_store_parity` / `verify_dual_store_readmodel_parity`,
  the `any_store` fixture) rather than asserting it in prose.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran.** A bare
  "looks fine / LGTM" with no probe log is a **rejected review** for that area — show your work on
  clean code too, including the fold sequences you constructed that folded *correctly*.
- A finding that is a **reliance** (the projector is correct only because a neighbor guarantees
  ordering/dedup/terminality) must **re-derive that neighbor's behavior from its code** and cite it;
  "assumed the store dedupes" is not sufficient — show the append path that does or does not.
- If the code contradicts the Atlas, an ADR, or a disclosed known-item, that disagreement is itself
  a finding (≥ P1) — the map being wrong is a defect.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: the
findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters | Proposed
action/Fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a clear statement
of **whether G-D's foundation gate may clear** (event sourcing is Wave-1 spine; because
`event-log-truth` is a human-gated surface, a BLOCK or an unresolved P0/P1 on the fold or the parity
mechanism holds the gate). State plainly anything you could not verify (e.g. a concurrent-append
ordering race you can reason about but not deterministically reproduce). Do **not** edit
`request.md`; do **not** push code fixes.
