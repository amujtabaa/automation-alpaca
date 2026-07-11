---
type: Review Request
rev_id: REV-0008
campaign_id: CAMPAIGN-0001
packet: ARCH
container_group: all + G-J (holistic architecture)
packet_lens: architecture (holistic: import contracts, seams, thin-client, coupling, dead-code)
status: AWAITING_REVIEW
targets: [all, G-J, .importlinter, ADR-005, ADR-006]
human_gated_surfaces: [order-submission, cancel-replace, kill-switch, manual-flatten, live-shadow-config, schema-db-migration]
# ^ An architecture violation can EXPOSE a gated surface without touching its logic —
#   e.g. the UI (or an unmigrated route) reaching a gated endpoint/store method directly,
#   bypassing the facade's quarantine/TradingState/event-log seams. That exposure is your
#   finding even though the gated command's *internals* are owned by another packet.
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [INV-070, INV-071, INV-072, INV-073, INV-074, "safety-core #4 (thin client)", "safety-core #5 (UI never calls Alpaca)", "safety-core #6 (UI owns no state)", "safety-core #7 (all important logic in backend)", INV-052, "spine INV-1..9"]
adr_in_scope: [ADR-005, ADR-006, ADR-004]
# ADR-005 = API facade + import-boundary plan; ADR-006 = import-linter enforcement (the ADR
# BEHIND the 5 contracts — load-bearing for this packet, NOT the mypy gate, which is ADR-007);
# ADR-004 = event-log-as-truth (the store->projector "depends up" seam below).
created: 2026-07-10
---

# Review Request REV-0008 — Holistic architecture (import contracts, seams, boundaries), architecture lens

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **zero correctness claims** — code beats the atlas, and if they
disagree that is itself a finding). You have the full repo at the frozen SHA.

This is the **holistic architecture packet**. You do not own one container's internal logic — you
own the **structure that holds the containers together**: the five machine-enforced import
contracts, the load-bearing seams between layers, the thin-client boundary, and the coupling /
dead-code / god-module smells that cut across packets. Your verdict answers one question: **does
the enforced structure actually match the documented target architecture** (CLAUDE.md "Boundaries
and stack", ADR-005/006, the spine spec, the `.importlinter` contract *intent*) — or is there an
unencoded rule, a leaky seam, or a technically-satisfied-but-intent-violated boundary that the
green linter hides?

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these — the SEAM/CONTRACT level):**
- `.importlinter` — the five contracts (names/types/source-and-forbidden lists), and whether they
  **completely** encode the intended layer model, or leave an unencoded rule an import (or a raw
  HTTP/URL reach) could violate while `lint-imports` stays green.
- `tests/test_import_boundaries.py` — the INI-independent grimp re-proofs. Do they prove what the
  INVs *state*, or only what the INI *says* (X-002)?
- The load-bearing seams: `app/facade/store_backed.py` → `app.monitoring.cancel_open_buys` (the
  ONLY facade→engine runtime edge); both stores → `app.events.projectors` (store "depends up" on
  projection, ADR-004).
- The thin-client boundary: `cockpit/*` (must not import `app.*`; reaches the backend only over
  HTTP via `cockpit/api_client.py`) — INV-071 / safety-core #4–#6.
- The facade **abstraction quality**: `app/facade/protocols.py` (re-export, 29 LOC) +
  `app/facade/commands.py` / `queries.py` (the `Protocol`s) vs `store_backed.py` (975 LOC impl) —
  does the typed port actually constrain the implementation, or is it a leaky abstraction?
- Coupling / god-module / dead-code / cycle-risk across `store_backed.py` (975), `monitoring.py`
  (2158), `store/core.py` (2160).

**Owned by other packets (follow leads freely into them; do not assume their contract holds):**
the *internal* logic of each container has a deep-coverage owner elsewhere — G-E engine (REV-0005),
G-B/C store (REV-0006/0009), G-D events (REV-0007), G-I facade+API (REV-0013), G-J cockpit
(REV-0015). You need not audit their internals exhaustively — but if the **architecture** relies on
a behavior those modules don't actually guarantee, re-derive it from their code and report the
reliance as **your** finding. And per follow-the-bug-anywhere: a concrete correctness bug you trip
over while tracing a seam is still your finding, **reported at its true location**.

## What you're reviewing
The Spine v2 layer model, as documented and as enforced:
```
cockpit (Streamlit UI) ──HTTP──▶ app.api ──▶ app.facade ──▶ { app.store, app.<engine>, app.broker, app.marketdata }
                                                             └─────────── all over app.models / app.config (leaf kernel)
```
Five contracts in `.importlinter` are meant to make that diagram non-negotiable: (1) the Alpaca SDK
is confined to two concrete ports, (2) the cockpit imports no `app.*`, (3) the engine is
venue-agnostic, (4) `app.models` is a leaf, (5) API routes reach the backend only via the facade.
`lint-imports` reports **`5 kept, 0 broken`** at the frozen base. Your job is **not** to confirm the
linter passes — it does. Your job is to find where a *green linter* and the *intended architecture*
part ways: an unencoded rule, a hand-maintained source list that a new module escapes, a boundary
that only checks `import` statements while the real coupling flows through HTTP, a duplicated
predicate, an abstract port so loosely typed it constrains nothing, or a seam that drags one layer
into another's runtime.

Run for context (read at `b600101`, do not review a drifting HEAD):
`git show b600101:.importlinter` · `git diff b600101~1..b600101 -- .importlinter tests/test_import_boundaries.py app/facade/`

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
- **The five contracts** (`.importlinter`, all verified present at `b600101`):
  `alpaca-sdk-confined-to-adapter` (`:33`, `type = forbidden`), `cockpit-is-a-thin-client` (`:51`),
  `engine-is-venue-agnostic` (`:66`, source list `:70-81`, forbidden list `:82-88`),
  `models-is-a-leaf` (`:95`, forbidden list `:102-120`), and
  `api-routes-reach-backend-only-via-facade` (`:134`, `unmatched_ignore_imports_alerting = error`
  at `:138`, source list `:139-147`, forbidden list `:148-162`). Note that contracts 3 and 5
  enumerate their source modules **by hand** — map that list against reality.
- **The INI-independent re-proofs** (`tests/test_import_boundaries.py`): the hand-maintained
  mirror sets `_ENGINE_PACKAGES` (`:64`), `_CONCRETE_VENUE_MODULES` (`:54`),
  `_SANCTIONED_ALPACA_REACHERS` (`:45`) — and the grimp assertions that consume them
  (`test_engine_never_reaches_a_concrete_venue_implementation` `:142`,
  `test_only_sanctioned_modules_transitively_reach_the_alpaca_sdk` `:124`). Ask: does a set drift
  from the contract it "mirrors"?
- **The only facade→engine runtime edge:** `from app.monitoring import cancel_open_buys`
  (`app/facade/store_backed.py:79`), called in `create_exit` (`:815`) and
  `emergency_reduce_override` (`:957`). The docstring at `:798` claims the broker call is
  "best-effort ... never under the store lock" (INV-052). The facade also imports engine-layer
  modules directly: `app.features` (`:50`), `app.policy` (`:68`), `app.protection` (`:80`).
- **The store "depends up" on projection:** `from app.events.projectors import (...)` in
  `app/store/sqlite.py:68` and `app/store/memory.py:52` (ADR-004: legacy tables are read-model
  projections of the event log). Trace the direction: does anything in `app.events` import back
  into `app.store` (a cycle), and is "store below events" the intended layering?
- **The typed port vs its implementation:** `app/facade/protocols.py` (`:19-21`, re-exports the two
  `Protocol`s). `ExecutionCommandFacade` (`app/facade/commands.py:35`) and `ExecutionQueryFacade`
  (`app/facade/queries.py:18`) — every method is annotated `-> Any` with `Any`-typed params (e.g.
  `commands.py:85-96` `inject_mock_candidate`, `queries.py:41` `get_review(target_date: Any)`).
  The concrete `store_backed.py` returns concrete DTOs (`create_exit -> FlattenResponse` `:789`,
  `cancel -> Order` `:838`). Note also: the module-level docstrings in `commands.py`/`queries.py`
  say "As of Phase 1 ... every other method still raises `NotYetImplementedError`", while the
  per-method docstrings say "real as of P6a/P6c/P6e" — read both.
- **The authoritative-predicate re-run in the facade:** `approve_candidate` re-runs the store's
  own risk predicates "for UX" — `limit_price_reason` (`store_backed.py:718`),
  `order_intent_block_reason` (`:735`), `risk_limit_reason` (`:746`) — the comment at `:738` says
  it "mirrors the authoritative store check exactly", then calls the authoritative
  `create_order_for_candidate` (`:761`).
- **The thin-client HTTP surface:** `cockpit/api_client.py` — the ONLY backend contact. It issues
  raw HTTP to gated endpoints directly: `set_kill_switch` (`:178` → `POST /api/controls/kill-switch`),
  `flatten_position` (`:119` → `POST /api/positions/{symbol}/flatten`), `cancel_order` (`:138`),
  `approve_candidate` (`:85`), `create_mock_candidate` (`:93` → `POST /api/dev/candidates`). Note
  no `X-Actor` header is ever sent.
- **The oracles** (check code against THESE, not the pinning tests): `docs/INVARIANTS.md`
  INV-070 (`:393`), INV-071 (`:407`), INV-072 (`:417`), INV-073 (`:428`), INV-074 (`:437`);
  ADR-005 (`docs/adr/ADR-005-api-facade-boundaries.md`); ADR-006
  (`docs/adr/ADR-006-import-boundaries.md`, esp. the Tier-1/Tier-2 split and "Finding 1"
  transitive-reach reasoning); ADR-004 (`docs/adr/ADR-004-event-log-truth-migration.md`); and
  CLAUDE.md "## Boundaries and stack" + the safety core (#4 thin client, #5 UI never calls Alpaca,
  #6 UI owns no state, #7 all important logic in backend).

## Probe checklist (find the gap, or prove it cannot exist — symmetric challenges)
Every probe is symmetric: **find an import path / coupling / reach that violates the intended
architecture but passes the linter, OR prove the five contracts fully encode the layer model for
that cluster.** Clean is a valid result — but you must show the probe you ran.

**CONTRACT-COMPLETENESS**
1. The source lists in contracts 3 (`engine-is-venue-agnostic`, `.importlinter:70-81`) and 5
   (`api-routes-reach-backend-only-via-facade`, `:139-147`) are **enumerated by hand**. Enumerate
   the actual `app/api/routes_*.py` files and the actual engine modules and diff them against the
   contract lists. Is any current module missing (an unguarded route/engine module today)? More
   importantly: does a **newly added** route file or engine module get *silently* exempted until
   someone edits the INI — i.e. is the contract "opt-in by name" where the intent is "all routes /
   all engine modules"? Construct such a module and show `lint-imports` stays green, or argue the
   enumeration is complete-and-maintained by another mechanism.
2. Contract 1 forbids the *import statement* `import alpaca` (`:40-44`). The **intent** (INV-070,
   safety-core #5) is "nothing but the adapter talks to the venue." Can a non-adapter module reach
   Alpaca **without importing the SDK** — a raw `requests`/`httpx` call to the Alpaca REST/stream
   URL, or importing a thin wrapper that itself is the sanctioned importer? Show a reach that
   satisfies the contract but violates the intent, or prove the SDK is the only venue path.
3. Contract 4 (`models-is-a-leaf`) forbids `app.models` importing listed layers (`:102-120`).
   Is the forbidden list **exhaustive** over `app.*`? Is any real `app` submodule absent from it
   (so `app.models` could import it and stay green)? Confirm `app.config` is handled correctly
   (it's listed `:118`) and that no back-edge cycle is possible via a module the list omits.

**SEAM-JUSTIFICATION**
4. `store_backed.py` imports `cancel_open_buys` from the single-writer engine `monitoring.py`
   (`:79`) — the only facade→engine *runtime* edge. Is it **minimal and justified**, or does it
   pull the facade into the engine's runtime responsibilities? Verify the INV-052 claim at `:798`
   (the broker call inside `cancel_open_buys` is never made under the store lock) **from the code**,
   across both call sites (`:815` create_exit, `:957` emergency_reduce_override). Find a lock-held
   broker call reachable through this edge, or prove the claim holds.
5. Both stores import `app.events.projectors` (`sqlite.py:68`, `memory.py:52`) — a store "depends
   up" on the projection layer (ADR-004). Is that direction **sound**, or is it an inverted seam
   (should projection depend on the store's raw event rows, not vice-versa)? Prove there is **no
   import cycle** `store ↔ events` at `b600101`, or exhibit one. Is the dependency a leaky
   abstraction (the store folding events it also writes)?

**THIN-CLIENT / BOUNDARY**
6. The import contract (contract 2) proves `cockpit ↛ app`. But the *architecture* intent is
   broader: safety-core #6 "the UI owns no strategy/risk/order/fill/position state" and #4 "thin
   client — observes state, issues intents, never mutates directly." An import contract cannot see
   HTTP. Audit `cockpit/app.py` + `cockpit/api_client.py`: does the UI compute any
   strategy/risk/order/position **logic** locally (sizing, floor math, lifecycle classification,
   "which statuses are open") that the backend should own — logic that would pass contract 2 while
   violating #6? Find it, or show the UI renders backend-classified data verbatim.
7. `cockpit/api_client.py` calls **human-gated** endpoints directly over HTTP (kill-switch `:178`,
   flatten `:119`, cancel `:138`, approve `:85`, dev-inject `:93`). An import contract says nothing
   about *which* endpoints the UI may reach. Is there an architecture rule (a gated surface that
   should route through an approval/confirmation seam, not a bare client call) that the import
   layer cannot enforce and nothing else does? Note the missing `X-Actor` header — does the audit
   trail lose the actor at this boundary (an architecture-level observability gap)? Report the
   exposure with its true location.

**PROTOCOL-DRIFT**
8. `ExecutionCommandFacade` / `ExecutionQueryFacade` type **every** method `-> Any` with `Any`
   params (`commands.py:50-128`, `queries.py:21-134`). A `Protocol` typed entirely as `Any`
   structurally matches *any* implementation — mypy cannot detect a return-type or signature drift
   between the port and `store_backed.py`'s concrete DTO returns. Is this a **leaky abstraction** (a
   contract "satisfied" technically — the impl `isinstance`-passes the `@runtime_checkable`
   Protocol — while the *intent*, a typed seam the routes depend on, is not actually enforced)?
   Show a signature/return drift mypy would miss, or argue the `Any` typing is a deliberate,
   safe migration-era choice with the real contract enforced elsewhere.
9. Cross-check every `store_backed.py` method against its Protocol declaration: does each real impl
   method's **name and keyword params** match the Protocol (`commands.py`/`queries.py`)? Is any
   Protocol method unimplemented-yet-wired, or any impl method not on the Protocol (an off-contract
   backdoor a route could call)? Also flag the module-docstring-vs-method-docstring contradiction
   (Phase-1 "still raises NotYetImplementedError" vs per-method "real as of P6x") as a docs-coherence
   finding if it misleads a reader about the enforced surface.

**COUPLING / DEAD-CODE**
10. `store_backed.py` (975), `monitoring.py` (2158), `store/core.py` (2160) are the largest modules.
    Is any a **god-module** doing multiple layers' jobs (e.g. the facade re-running engine
    predicates at `:718/735/746` — is that risk logic that belongs in the backend/store per
    safety-core #7, duplicated into the facade where it can **drift** from the authoritative
    `create_order_for_candidate` at `:761`)? Prove the duplicated predicates are provably identical
    today, or show an input where the facade pre-check and the store's authoritative check disagree
    (a UX-vs-truth divergence).
11. Hunt for **dead / unreachable code** and **hidden cross-layer reaches** the linter misses:
    an `app.*` module imported by nothing (dead), a `TYPE_CHECKING`-only import that masks a real
    runtime coupling (`store_backed.py:109-113`), or a concrete type passed through an abstract
    port (a leaky port — an engine returning a concrete-adapter object the caller must down-cast).
    Find one, or state the null result with the grep/graph query you ran.

## Independent-oracle hooks (check code against the STATEMENT / INTENT, not the linter — X-002)
The core trap for this packet: **a passing linter with an incomplete contract is exactly the gap to
hunt.** `lint-imports` reporting `5 kept, 0 broken` is *provenance, not proof* — it proves the
contracts-as-written hold, not that the contracts encode the architecture. So:
- Check the code against the **invariant statements** in `docs/INVARIANTS.md` (INV-070…074) and the
  **ADR intent** (ADR-005 "routes must not directly mutate stores, call broker adapters, call
  monitoring helpers, or inspect engine internals"; ADR-006 Tier-1/Tier-2 reasoning) and the
  **CLAUDE.md "Boundaries and stack"** target — **not** against `test_import_boundaries.py` passing.
- Per X-002, the pinning tests can assert the very gap they should catch (e.g. a hand-maintained
  mirror set in the test that drifts from the contract, or a grimp query scoped too narrowly). If
  the code (or a constructed module) contradicts an INV *statement* while every test stays green,
  that green-but-wrong state **is** the finding.
- If the code contradicts the Atlas, an ADR, or a disclosed known-item, that disagreement is itself
  a finding (≥ P1) — including "the map/ADR says the boundary is fully enforced; here is a reach it
  does not cover."

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro plus its pasted output**. For this packet that
  means one of: a constructed module + `lint-imports` output showing it stays green while violating
  intent; a `grep`/`grimp` query proving a cross-layer reach or cycle; a `python -m pytest -k
  test_import_boundaries` run; a mypy invocation showing a drift it cannot catch; or a diff of a
  hand-maintained list against reality. A finding with no repro is marked **"unverified concern"**
  and **cannot gate**.
- You **may** run `lint-imports`, `python -m pytest tests/test_import_boundaries.py`, `mypy app/`,
  and `grimp` queries to ground findings — they are static, network-free (Rule 9).
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the grep,
  the constructed module, the graph query). A bare "boundaries look fine / LGTM" with no probe log
  is a **rejected review** for that cluster — show your work on clean contracts too.
- Pin the environment (Python 3.12, frozen base `b600101`) in your result; mark any
  environment-dependent result as such.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0008/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and an explicit
statement of **whether the architecture-foundation gate may clear** (does the enforced structure
match the documented target, or is there an unencoded/leaky boundary that must be closed first).
State plainly anything you could not verify. Do **not** edit `request.md`; do **not** push code fixes.
