# CAMPAIGN-0001 — Codebase Atlas (shared reviewer context)

> **What this is.** A structural map of the repository for the cross-model review campaign.
> It tells you *where things are, how they're layered, and which oracle to check against* —
> so every reviewer starts from the same ground. It is authored by the code's author (Claude)
> for the independent reviewer (Codex).
>
> **What this is NOT.** It makes **zero correctness claims**. It never says a thing is "safe",
> "handled", or "correct". If you want to know whether something holds, you check the code
> against the linked oracle (`docs/INVARIANTS.md`, the ADRs, `CLAUDE.md` safety core) — not
> against this file, and not against the pinning tests (see the X-002 rule below).

---

## Anti-bias rules (read before you use this atlas)
1. **Structure only, no verdicts.** This atlas maps and points; it asserts nothing about
   correctness. Do not treat "the atlas didn't flag it" as evidence of anything.
2. **Code beats the atlas.** If the code disagrees with anything here, the code is truth **and
   the disagreement is itself a finding** (at least P1 — the map is wrong).
3. **Disclosed issues are calibration, not answers.** The "Disclosed known-open items" section
   lists things the author already suspects. They are there so you can confirm your probing
   works by independently re-finding the ones in your scope — **not** so you rubber-stamp them.
   They are **not** a complete list, and re-finding one is a floor, not a ceiling.
4. **No leading hypotheses.** Your packet's probe checklist is framed as symmetric challenges
   ("find X, or prove it cannot exist"), never "confirm that X is broken." Hunt for what is
   *not* listed.

---

## Frozen base + environment (pin these in every result)
- **Frozen base SHA:** `b60010148f3201a9f8c62ee0bda45371d5c964f4` (`master` tip; short `b600101`).
  Review THIS commit. Do not review a drifting HEAD — findings must be comparable across packets.
- **Python: 3.12.** (A prior review round produced spurious failures under Python 3.14 —
  SQLite `ResourceWarning`s promoted to errors in unrelated tests. Use 3.12; if you cannot,
  say so explicitly and mark environment-dependent results as such.)
- **Install:** `pip install -r requirements.txt -c constraints.txt` (exact pinned closure).
  `alpaca-py` is optional (lazy-imported); tests that need it `importorskip("alpaca")`.
- **The gates CI runs** (`.github/workflows/ci.yml`): `ruff check .` · `mypy app/` ·
  `lint-imports` (import-linter) · `pytest --cov=app --cov-branch` (coverage floor 93).
  You may run any of these to ground a finding.

---

## Layer model (enforced, not aspirational)
```
cockpit (Streamlit UI) ──HTTP──▶ app.api ──▶ app.facade ──▶ { app.store, app.<engine>, app.broker, app.marketdata }
                                                             └─────────── all over app.models / app.config (leaf kernel)
```
The boundaries are **machine-enforced** by `/.importlinter` (run as `lint-imports` in CI and
pinned by `tests/test_import_boundaries.py`). The 5 contracts — your architecture oracle:
1. **alpaca-sdk-confined-to-adapter** — only `app/broker/alpaca_paper.py` and
   `app/marketdata/alpaca_stream.py` may `import alpaca` (INV-070).
2. **cockpit-is-a-thin-client** — `cockpit/*` may not import `app.*` at all (INV-071).
3. **engine-is-venue-agnostic** — engine modules may use abstract ports, never a concrete
   adapter/SDK (INV-072).
4. **models-is-a-leaf** — `app/models.py` imports no other `app` layer (INV-073).
5. **api-routes-reach-backend-only-via-facade** — the route modules reach the backend only
   through `app.facade` (INV-074 / ADR-005); punch-list empty, ratcheted.

---

## Your scope — follow the bug anywhere
Your packet names a **container** (a group below) and a **lens**. That assignment defines where
your **verdict and guaranteed deep coverage** live — the area you must probe exhaustively and
sign off on, so nothing falls through the gaps between packets. It is **not a fence.**

- **You have the full repo at the frozen SHA, and you are encouraged to chase any lead across
  container boundaries, to whatever depth the investigation needs.** If a defect in your
  container is *caused* by, or *reaches into*, another module — the store, the projector, the
  broker adapter, a kernel predicate — follow it there and report it. **A bug is your finding
  wherever it lives**, including inside another packet's container.
- **A "not-my-container" defect is still a finding.** Never drop a real hazard because another
  packet nominally owns the file. Report it with its true location; the synthesis routes it.
- **Do not assume a neighbor's contract holds just because another packet owns it.** If your
  container *relies* on a behavior a neighboring module does not actually guarantee, that
  reliance is **your** finding — re-derive the behavior you depend on from that module's code,
  don't take its docstring or this atlas on faith.
- **Duplication across packets is fine — it is signal, not waste.** Two reviewers landing on the
  same defect from different containers is *corroboration*; the synthesis dedups and treats
  agreement as **higher** confidence. Never stay silent to avoid overlap.
- The cross-container **REV-0004 ATTACK-CHAIN** packet additionally owns whole-surface,
  end-to-end hunting (each safety invariant traced across every layer) — but that does not
  narrow your own license to roam.

The only thing your container fences **in** is responsibility: you cannot mark your area
"reviewed" by punting its hard parts to a neighbor. Coverage is owned; investigation is free.

---

## Container-group map (who owns what)
Each group is a bounded review unit. **"Owner" = the packet responsible for that group's deep
coverage and verdict** — *not* a boundary other reviewers must stop at (see "Your scope — follow
the bug anywhere" above). Any packet may report a defect it finds in any group; the owner is
simply who guarantees the group is probed and signed off. LOC ≈ source lines.

| Group | Files (key) | ~LOC | Owner packet |
|---|---|---|---|
| **G-A** Kernel + predicates | `app/models.py`, `app/transitions.py`, `app/policy.py`, `app/position.py`, `app/features.py`, `app/protection.py`, `app/config.py` | ~2,500 | REV-0010 KERNEL |
| **G-B** Store contract + planners | `app/store/base.py` (ABC, 55 methods), `app/store/core.py` (planners) | ~3,340 | REV-0006 STORE-SPEC |
| **G-C** Store impls + parity | `app/store/memory.py`, `app/store/sqlite.py`, `app/store/__init__.py` | ~5,650 | REV-0009 STORE-IMPL |
| **G-D** Event sourcing | `app/events/projectors.py`, `app/events/replay.py` | ~720 | REV-0007 EVENTS |
| **G-E** Runtime engine | `app/monitoring.py` (single-writer async heart), `app/reconciliation.py` | ~2,515 | REV-0005 ENGINE |
| **G-F** Strategy + approval | `app/strategy.py`, `app/strategy_loop.py`, `app/approval/*` | ~610 | REV-0014 STRATEGY |
| **G-G** Broker adapters | `app/broker/adapter.py`, `alpaca_paper.py`, `mock.py`, `sim.py`, `factory.py` | ~1,490 | REV-0011 BROKER |
| **G-H** Market-data | `app/marketdata/service.py`, `alpaca_stream.py`, `fake.py`, `factory.py` | ~710 | REV-0012 MARKETDATA |
| **G-I** Facade + API + root | `app/facade/*` (`store_backed.py`=975), `app/api/*`, `app/main.py` | ~2,630 | REV-0013 FACADE-API |
| **G-J** Cockpit + boundary | `cockpit/app.py`, `cockpit/api_client.py` + the API contract it consumes | ~850 | REV-0015 UIUX |
| **G-K** Tests + governance + deps | `tests/**` (113 files), `docs/**`, `pkl/**`, `.ai-os/**`, `requirements.txt`/`constraints.txt`/`pyproject.toml`, `.github/workflows/`, `harness/*`, `.importlinter` | — | REV-0016 QA + REV-0017 GOV |

**Cross-cutting (spanning packets own these, not one group):**
- **REV-0004 ATTACK-CHAIN** traces each safety invariant *end-to-end across* G-A…G-I.
- **REV-0008 ARCH** owns the layer/boundary structure (the 5 contracts, seams, coupling) across
  backend **and** frontend.
- Load-bearing seams to watch: `app/facade/store_backed.py` imports
  `app/monitoring.py::cancel_open_buys` (the only facade→engine runtime edge); both stores
  import `app/events/projectors.py` (store depends "up" on projection — ADR-004).
- Cross-cutting kernel modules imported nearly everywhere: `app/models.py` (leaf),
  `app/config.py`, `app/policy.py`, `app/transitions.py`.

---

## Oracles (check code against THESE, as links — do not trust summaries)
- **`CLAUDE.md`** — the always-on **safety core** (11 numbered invariants + the human-gated
  surfaces + the layering + the conflict rule). The top-level spec everything defers to.
- **`docs/INVARIANTS.md`** — the **independent invariant registry**, INV-001…INV-075 (each with
  *statement / why / pinned-by*). Written to be read *without* its pinning tests.
- **`docs/adr/ADR-001…ADR-008`** — the 8 accepted architecture decisions (overfill quarantine,
  timeout quarantine, manual flatten, event-log truth, facade + import boundaries, mypy gate,
  order-status provenance).
- **`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §5** — the spine invariants **INV-1…INV-9**
  (⚠ a *separate* numbering from the INV-0xx registry — see the ID-collision item below).
- **`docs/MIGRATION_MATRIX.md`** — ⚠ self-labeled **HISTORICAL/STALE**; it points to
  `pkl/process/migration-history.md` as the corrected truth. Do not treat it as current.
- **`.importlinter`** — the 5 machine-enforced contracts (architecture oracle).
- **`AGENTS.md` ("## Review guidelines")** + **`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`**
  — your role, the P0/P1 rubric, the verdict vocabulary.

### The X-002 rule (why the registry, not the tests)
A test can assert the very bug it should catch (the on-the-record example: an ADR required a
self-heal, the code didn't do it, and the test pinned the buggy result as "correct" — X-002,
now guarded by INV-033). **So probe the code against the INVARIANT STATEMENT in
`docs/INVARIANTS.md`, not against the pinning test.** "Pinned by" is provenance, not proof.

---

## Glossary (Spine v2 vocabulary you'll meet)
- **Event-truth / read-flip** — state is derived by folding the append-only `execution_events`
  log; the legacy column is a co-written read-model (ADR-004; order-status flip was WO-0007b).
- **Single-writer** — only the Execution Engine (`app/monitoring.py`, under the store lock)
  mutates order/fill/position state (safety core; INV-050/051).
- **Claim gate** — `claim_order_for_submission`: the CREATED→SUBMITTING transition that is the
  double-submit guard (INV-021; hardened in WO-0013).
- **TIMEOUT_QUARANTINE** — an ambiguous/timed-out broker submit is quarantined and reconciled
  via a deterministic `client_order_id`, never blind-resubmitted (ADR-002).
- **Deferral** — a manual flatten to a genuinely in-flight protection order is *deferred*, not
  double-exited or blind-cancelled (ADR-003 / INV-034/036; WO-0015 made it operator-visible).
- **Dual-store parity** — `InMemoryStateStore` and `SqliteStateStore` must behave identically;
  proven via the `any_store` fixture and `app/events/replay.py` (INV-050/051).
- **Latest-lifecycle-event-wins** — the order-status projector folds by append sequence, not by
  authority (ADR-008 "Truth model"; INV-075).
- **Human-gated surface** — order submit, cancel/replace, kill switch, manual flatten,
  live/shadow config, schema/DB migration, event-log-truth changes, deletion of tests/docs/ADRs
  — never auto-approved (`CLAUDE.md`).

---

## Disclosed known-open items (CALIBRATION, not answers — see anti-bias rule 3)
The author already suspects the following. **Independently confirm / expand / refute the ones in
your scope** as a check that your probing works. This is deliberately **incomplete** and carries
**no verdicts** — the real findings are the ones NOT on this list.
- **INV-034 flatten** — a tracked-but-unfixed flatten/live-protection interaction behind a
  "flaky `TestSqliteLifecycle`" (`work/review/FINDING-flatten-inv034-live-protection.md`);
  explicitly *not* to be hidden behind a version pin. Confirm current behavior.
- **Actor is always `"operator"`** — the cockpit never sends the `X-Actor` header, so the
  audit actor carries no distinguishing info in practice (`app/api/deps.py::get_actor`).
- **Cockpit UX gaps** — no emergency-reduce button (kill-switch → flatten returns 409, a
  dead-end); no close-session / reconciliation / sell-intent screens; no auto-refresh on live
  monitors; a dev-inject affordance renders in the operator UI; transport error strings shown
  verbatim to the operator.
- **Facade** — `store_backed.py` re-runs the store's authoritative risk predicate "for UX"
  (duplicated logic → drift risk); Protocol-vs-impl signature drift; some read routes skip the
  error→HTTP wrap (a future facade change there would surface as a raw 500).
- **Docs coherence** — the spine `INV-1..9` registry vs the `INV-001..075` registry **collide
  numerically**; `MIGRATION_MATRIX.md` is self-stale; a tri-state drift on the mypy grandfather
  burndown (pyproject "burned down" vs `WO-0012` still in `work/queue/` vs `testing-model.md`
  "16 grandfathered"); `CLAUDE.md` says "Python 3.12" but CI runs 3.11+3.12 and mypy pins 3.11.
- **Supply chain / build** — deps are `==`-pinned but **not hash-pinned**; no SBOM; **no
  `pip-audit`/Dependabot** despite a doc claiming a scan gate exists; the `.ai-os` + `harness/`
  checkers are **not CI-gated**; a `follow_imports=skip` mypy band-aid for numpy/pandas.
- **Test quality** — over-mocking hotspots (~5 files); the X-002 anti-pattern is a *named,
  documented* failure mode here; `conftest.py` and root `conftest.py` are byte-identical dupes.

### Wave-1 VERIFIED findings — already dispositioned + in remediation (do NOT re-file as new)
These were found by the Wave-1 packets, **independently reproduced in Python 3.12, and
dispositioned** (`work/review/REV-0004…0008/disposition.md`, `CAMPAIGN-0001/synthesis.md`). At the
frozen base `b600101` the code still exhibits them (fixes land on a separate branch). If your scope
touches one, **treat it as a known item — confirm/expand, don't re-report it as a fresh P0/P1**; a
genuinely *distinct* adjacent defect IS wanted.
- **ENG-001 (P1, in fix):** `_run_protection` caches `kill_switched` once (`monitoring.py:301`) and
  acts on it after an `await`, so a concurrent kill can let a `PROTECTION_FLOOR` intent+order be
  created under `HALTED`. Not a venue bypass (the claim gate blocks submission).
- **REV-0006-F-001 (P1, in fix):** `SqliteStateStore.flatten_position` commits in 4 transactions;
  a hard crash strands an `approved`-no-order intent (memory store is atomic). INV-050-statement
  violation; being made single-transaction.
- **UC-002 (P1, in fix):** operator `actor` dropped on the cancel audit event
  (`transition_order`/`plan_transition_order` carry only `{from,to}`).
- **P2s (batched):** timeout-quarantine queries not under the loop budget (`monitoring.py:952`);
  parity verifier omits order-status (`replay.py:121-141`, the disclosed deferral); `append_execution_event`
  has no production caller (write-path planners guard it — INV-075); bare `ValueError`→422 vs ABC
  `OrderTransitionError`→409; Contract-5 route/facade boundary latently bypassable via `get_store`
  (no current route does it); stale facade module docstrings. **UC-001 crash double-submit was
  REFUTED** (adapter `client_order_id` idempotency) — do not re-raise it.

---

## Packet roster (this campaign)
See the campaign README (`work/review/CAMPAIGN-0001/README.md`) for the full roster, waves, and
sequencing. Wave 1 (the safety-critical spine), run in this order under sequential execution:
**REV-0004 (ATTACK-CHAIN) → REV-0005 (ENGINE) → REV-0006 (STORE-SPEC) → REV-0007 (EVENTS) →
REV-0008 (ARCH)**. Each packet is a self-contained `work/review/REV-NNNN/` folder; you fill its
`result.md` from `.ai-os/templates/review-result.md`.
