---
type: Work State
work_order_id: WO-0139
status: ACTIVE
branch: codex/signal-r5b2-operator-auth
updated: 2026-07-25
---

# Signal R5b-2 state

[FABLE • FULL • verification: DIRECT • task: WO-0139 Signal R5b-2 operator enforcement]

## Continuity

After any pause or compaction, re-read in order:

1. The operator kickoff.
2. This state file.
3. `work/active/WO-0139-signal-r5b2-operator-enforcement.md`.

Then verify the live branch and worktree with `git log` and `git status`; do not reconstruct state
from conversation memory.

## Fable gate

```yaml
fable_gate:
  goal: "Require the local operator credential on every sensitive mounted request, bind audit attribution to the authenticated principal, add mutation-free signal reads, and preserve cockpit access to critical controls."
  assumptions:
    - "The WO-0139 rev-2 M1 decision block is pre-ratified; every load-bearing line is TRACED or INHERITED."
    - "R5b-1 is merged and REV-0042 is dispositioned; both hard-gate checks passed against the refreshed tree."
    - "The staged corpus is an incomplete RED input and the archive is design reference only; current code and the WO govern every adaptation."
    - "The feature flag remains OFF and remains independently un-enable-able until R6 and R7 satisfy the joint gate."
    - "Mutation-free lazy reads and the same-change 02-lifecycle.md amendment were ratified on 2026-07-25."
    - "flag_on_settings currently receives enable_dev_routes=True from the Settings default rather than an explicit helper pin; route bounds derive from the built settings object."
  approach: "Activate WO/state first, import and adapt the staged tests, record RED per slice, implement the minimum operator/auth/read/cockpit/spec changes, run targeted and full gates, stage REV-0043, and push only the delivery branch."
  out_of_scope:
    - "Rails enforcement, producer release, signal approve/reject, conversion, schema/migration, new event vocabulary, flag enablement."
    - "The deferred /api/producers read and the R6/R7 required-present completeness proof."
    - "Open-ended adversarial discovery; REV-0043 is the independent adversarial net."
  done_when:
    - "Literal REQUIRED existence and discovered-subset classification assertions cover the real mounted app."
    - "Missing/unknown credentials return 401, wrong-role credentials return 403, and only GET /api/health remains public under the flag."
    - "All 16 actor-consuming commands use principal-preferring attribution, including both migrated recovery routes and dual-store provenance proof."
    - "GET /api/signals uses a pure effective status with injected time and never appends on read."
    - "Cockpit headers merge the operator key without losing X-Actor; critical controls and sensitive reads remain usable."
    - "All named gate commands pass with fresh evidence; WO is REVIEW, REV-0043 request is staged, branch is pushed, and no PR/result/ledger/completion move exists."
  blast_radius: "Request-time middleware and request principal state; 16 command audit actors; one signal read route/facade; cockpit API headers; auto-doc exposure; lifecycle text; config template; dedicated route-matrix and signal-read test corpus."
```

## Decision block (verbatim from WO-0139 rev-2)

**Pre-checked = ratified on paste; edit a line to override.** Every line is `TRACED` or `INHERITED`;
no `ASSUMED` line is pre-checked. **⟨Step-0⟩** marks a claim that must be re-verified against the
merged R5b-1 tree before building — R5b-1 was in flight when this was drafted.

- [x] **D-R5b2-1 HARD predecessor gate.** R5b-1 merged to master **and REV-0042 dispositioned**.
      Verify: `git ls-tree master app/api/routes_signals.py` returns a blob **and**
      `work/review/REV-0042/disposition.md` exists. Else **STOP**. Branch
      `codex/signal-r5b2-operator-auth` from the merged master.
      — TRACED(ratified round-2 gate; `disposition.md` is the REV-0039/40/41 convention).

- [x] **D-R5b2-2 Scope = request-time operator enforcement** (boundary above). No rails enforcement,
      no release action, no conversion. — INHERITED(sequencing plan C-1/C-2).

- [x] **D-R5b2-3 The route-authorization matrix — TWO independent assertions over a LITERAL required
      set.** rev-1 derived the required set from discovery ("the routes mounted at R5b-2"), which is
      **circular: a set derived from discovery can never detect absence.** Spec `04:98-100` forbids
      exactly that — required routes are "asserted to **EXIST** … a required route silently unmounted
      **FAILS** (**not merely 'classify whatever is mounted'**)". Compounding it: deny-by-default
      http-middleware returns **401 for unmatched paths**, so a negative sweep alone passes for path
      templates that do not exist. Therefore the matrix asserts **both** directions:
      1. **EXISTENCE:** `REQUIRED ⊆ discovered`, where `REQUIRED` is a **literal hardcoded list of
         `(method, path)` pairs** in the test module (never computed from the app). A silently
         unmounted required route FAILS.
      2. **RATCHET:** `discovered ⊆ CLASSIFIED`. Any mounted route absent from the classification
         table FAILS, so R6/R7 cannot ship an unclassified route.
      Plus: every classified sensitive route returns **401** with no credential and **403** with a
      wrong-role credential; `GET /api/health` is the only public route.
      **This closes GAP-02 in full** — its three clauses (`THREAT_MODEL_SIGNAL_SEAT.md:112`) are all
      scoped to *mounted* routes and all satisfiable here. What defers to the **D-2a joint proof** is
      the distinct **spec-04 required-present completeness** obligation for **R6's release** and
      **R7's approve/reject** routes (deferred by `03-rails.md:121-126`: "authored across the WOs, run
      green at the joint milestone"). Add each to `REQUIRED` as its rung lands.
      — TRACED(spec `04:96-107`; `03-rails.md:121-126`; threat model `:112`; M4b F-1/F-7).

- [x] **D-R5b2-4 Route discovery: flattener + `openapi` cross-check + a DERIVED bound.** A naive
      `for r in app.routes: r.path` is **fail-OPEN**: measured on fastapi 0.139.0 / starlette 1.3.1,
      `app.routes` = **4 `Route` + 8 `_IncludedRouter` with `path is None`** → **zero** `/api` routes
      discovered and every assertion passes vacuously. Required: a **documented recursive flattener**
      (recursing `_IncludedRouter.original_router.routes` and `Mount.routes`), cross-checked against
      `app.openapi()`.
      **The bound must be DERIVED, never hardcoded as a magic number:** the count is
      configuration-dependent (34 `/api` with dev routes, **33** with `enable_dev_routes=False`, and
      `config.py:530` defaults it to `not has_creds`) and grows as rungs land. Derive it from the same
      `Settings` the test builds — `tests/signal_seat_helpers.py::flag_on_settings` pins
      `enable_dev_routes=True` — and condition the dev-route row on `settings.enable_dev_routes`.
      **Note the auto-docs routes are `include_in_schema=False`, so they are invisible to the
      `openapi()` cross-check** and must be asserted separately (D-R5b2-9).
      — TRACED(planning-seat measurement; archive `tests/test_signal_routes.py:391-437` already does
      the flattener + a bound; M4b F-3a/F-6.)

- [x] **D-R5b2-5 The actor-consuming set is 16 routes — enumerated BY GREP, not by `get_actor` call
      sites.** Fixing `get_actor` alone is **insufficient**. **14** routes take
      `actor: str = Depends(get_actor)` (`routes_system.py:51`; `routes_watchlist.py:40,64`;
      `routes_candidates.py:55,79`; `routes_trading.py:103,128,304,360,379`; `routes_dev.py:32`;
      `routes_controls.py:37,48,59`) and **2 bypass it entirely** with
      `actor: str = Header(..., alias="X-Actor", min_length=1)`:
      **`routes_trading.py:220`** (`POST /api/order-recoveries/{recovery_id}/fills` — ingests a
      canonical **fill**, invariant 9) and **`:246`** (`.../reconcile` — the human reconciliation
      **attestation**). Corroborated by exactly **16** `command_facade.*` call sites in `app/api/`.
      **Both direct-header routes MUST migrate** to the principal-preferring path, each with its own
      regression. Confirmed clean: no actor arrives via a body field (`app/api/schemas.py` has none),
      no facade default (`app/facade/commands.py` requires `actor` on all 16 methods), no
      websocket/`Mount` path; `COMMAND_ACTOR_SYSTEM` (`app/store/base.py:409`) is engine-loop only.
      — TRACED(grep, planning-seat re-verified: 14 + 2 = 16; archive `REV-0027/result.md:17-27` F-1).

- [x] **D-R5b2-6 Producer exemption matches an exact `(method, path)` pair — never a prefix — and so
      does the public-health exemption.** The archive skipped enforcement on
      `path.startswith("/api/signals")`, wrongly exempting operator-only signal routes and never
      stamping the principal. Only **`POST /api/signals`** is producer-only; **`GET /api/signals` is
      operator-only**, so path-only matching would exempt it. The archive's public exemption is
      likewise `path in _PUBLIC_PATHS` (`main.py:78,267`) — tighten it to exact `(method, path)` so
      e.g. `POST /api/health` is not silently public. Required negatives: `GET /api/signals` with a
      producer key ⇒ 403, with none ⇒ 401. **⟨Step-0⟩** confirm R5b-1's actual mounted method/path.
      — TRACED(archive `REV-0027/result.md:17-27`; spec `04 §1a:90-91`; M4b F-15).

- [x] **D-R5b2-7 Enforcement covers sensitive READS; these five were missed by earlier enumerations:**
      **`GET /api/events`** (`routes_trading.py:329` — **the audit event log**, event-log-truth read
      exposure), `GET /api/protection`, `GET /api/sell-intents`, `GET /api/reconciliation`,
      `GET /api/operator/orders`. **`POST /api/session/close` is operator-only** — a mutating command,
      not a read. `GET /api/health` is the only public route.
      — TRACED(measured inventory; spec `04 §1a:81`).

- [x] **D-R5b2-8 GAP-01 — cockpit plumbing ships in the SAME change and MERGES headers.**
      `cockpit/api_client.py::_request` (`:28`) is the **only** outbound path (verified: `cockpit/` is
      3 files; sole `requests` use at `:31`; `cockpit/app.py` imports only `api_client`). Inject
      `X-Operator-Key` from the environment **merged with**, never replacing, per-call `headers=`. Two
      call sites pass `headers={"X-Actor": actor}` (`:165`,`:178`) and `X-Actor` is **required** at
      `routes_trading.py:220,246` — measured: a missing/blank header is a **422**, so a replacing
      implementation fails loudly on exactly the two migrated routes. The cockpit **must NOT import
      `app.config`** (import-linter contract 2): hardcode `"OPERATOR_API_KEY"`. **Prove no lockout:**
      kill switch, flatten, session controls, and sensitive reads all usable with the configured key
      (invariant 11).
      — TRACED(`cockpit/api_client.py:28,31,165,178`; `.importlinter` contract 2; GAP-01 `:111`, T-22).

- [x] **D-R5b2-9 Auto-docs coverage is NOT free — bind it to the layer that actually covers it.**
      rev-1 claimed deny-by-default gives operator-only docs automatically. **Refuted:** with
      FastAPI-**dependency** enforcement, `/openapi.json`, `/docs`, `/redoc`,
      `/docs/oauth2-redirect` return **200** (they are added by FastAPI itself, not via
      `include_router`). Only **http-middleware** enforcement 401s them. So either:
      (a) enforce in `@app.middleware("http")` — covers docs and unmatched paths; or
      (b) explicitly disable: `docs_url=/redoc_url=/openapi_url=None` under the flag (the archive's
      choice: `docs_on = not settings.signal_seat_enabled`, `main.py:224-232`).
      **Whichever you choose changes the total operation count**, so reconcile it with D-R5b2-4's
      derived bound. Spec `04:101-104` requires ABSENT-or-operator-only, **never public** — assert it.
      — TRACED(M4b F-3, measured; archive `main.py:224-232`).

- [x] **D-R5b2-10 `root_path` divergence — defense-in-depth, and do not import a private symbol.**
      Starlette 1.3.1 routes on `get_route_path(scope)` which **strips `root_path`**, while
      `request.url.path` does not (measured: `/prefix/api/signals` vs `/api/signals`). An exact-string
      exemption computed from `request.url.path` would stop matching behind a path prefix.
      **However** the sanctioned launcher `app/server.py::run()` (`:43-80`) never passes `root_path`
      to uvicorn, so this is **not reachable today** — treat it as defense-in-depth, not a live break.
      Compute the routed path **inline** (`p = scope["path"]`, minus `scope.get("root_path","")`);
      do **not** import `starlette._utils.get_route_path` (private, no `__all__`). Add a `root_path`
      regression.
      — TRACED(`starlette/_utils.py:96`; `app/server.py:43-80`; M4b F-10).

- [x] **D-R5b2-11 Complete the truncated crown-jewel audit test — with an EXACT-equality assertion
      against a DISTINCT principal.** Staging's `tests/test_signal_routes.py` ends **mid-comment
      (`# The forged X-Ac`) at byte 14628**; its last statement is
      `assert events, "no kill-switch audit event was written"`, so it **parses, collects, and passes
      while asserting nothing about the actor**. Two required properties:
      1. The recorded actor **equals** the composed principal-led form **exactly** — not merely
         `actor != forged`, which passes for `"operator:evil"` or `"evil:operator"`.
      2. **The principal must be a DISTINCT identifier.** The archive stamps
         `authenticated_actor = DEFAULT_ACTOR` (`main.py:281`), byte-identical to the flag-off default
         (`deps.py:23`) — which makes a flag-on authenticated event **indistinguishable** from an
         unauthenticated one. That is itself an *audit-attribution defect* on this WO's crown jewel.
         Stamp something distinguishable (e.g. an `operator:<key-id>` form) and assert it.
      — TRACED(staged byte count/EOF verified; archive `main.py:281` vs `deps.py:23`; M4b F-8).

- [x] **D-R5b2-12 `.env.example` documents the credential surface.** It currently documents **none**
      of `SIGNAL_SEAT_ENABLED`, `OPERATOR_API_KEY`, `SIGNAL_PRODUCER_KEYS` (grep: zero hits),
      violating the primer's "safe, complete configuration template" contract the moment the flag is
      real. Add all three with **blank/placeholder values**; never commit real credentials.
      — TRACED(`.env.example` grep; repo primer §Environment Variables).

- [x] **D-R5b2-13 Flag stays OFF; flag-off byte-equivalent — INCLUDING the `X-Actor` sanitization
      carve-out.** With the flag off: enforcement inert, existing localhost no-auth posture unchanged,
      **no existing test edited**, `harness/bootstrap.py` green. **The trap rev-1 dropped:** the
      archive `get_actor` applies `"".join(ch for ch in raw_label if ch.isprintable())` to `X-Actor`
      **unconditionally** (archive `deps.py:121-125`), whereas master returns the stripped header
      verbatim (`deps.py:87-89`). That is a **flag-independent behavior change** and **no existing
      test covers control characters**, so the specified gate battery cannot detect it. Therefore:
      scope the sanitization **under the flag**, and add a **flag-off regression asserting `get_actor`
      returns a control-character `X-Actor` unchanged**. (`load_settings()` reads the flag from the
      environment, `config.py:535-536` — there is no source-level guard, so flag-off must be tested
      explicitly.)
      — TRACED(archive `deps.py:121-125` verified; master `deps.py:87-89`; M4b F-4; WO-0138:164-167).

- [x] **D-R5b2-14 Dual-store parity for the actor migration — with an app per store.** The two
      migrated routes write **event truth**. Their actor-provenance regressions run on **both** stores.
      Note `any_store` lives at **`conftest.py:29`** (repo root — there is **no** `tests/conftest.py`)
      and yields a **raw store**, not an app; an HTTP-level actor-provenance test must **construct an
      app per store variant**. — TRACED(`conftest.py:29`; M4b F-9).

- [x] **D-R5b2-15 `/api/producers` read is DEFERRED — not implementer judgment.** rev-1 said "only if
      trivially derivable", which is not ratifiable on a human-gated auth surface. `app/store/base.py`
      exposes only `ingest_signal`/`get_signal`/`list_signals` (`:1315-1356`) — there is **no producer
      accessor**, and only `PRODUCER_QUARANTINED` exists in `app/models.py:483`. The read lands with
      **R6**, which owns producer state. Add it to `REQUIRED` then.
      — TRACED(`app/store/base.py:1315-1356`; `app/models.py:483`; M4b F-13).

- [x] **D-R5b2-16 `GET /api/signals` is NOT a one-liner — and R5b-2 now owns the WHOLE read half.**
      It needs `effective_signal_status` — which **exists nowhere in the repo** (verified) — plus an
      **injected clock** (lazy TTL reclassification on read) and facade `list_signals`/`get_signal`
      (archive `facade/signals.py:47,129`). No bare `datetime.now()`.
      **rev-3 addition (from the R5b-1 NEEDS-INPUT disposition):** R5b-2 also inherits **the entire
      `tests/test_signal_facade_reads.py` corpus**, the facade read methods, and any ingest test that
      reads back through `GET /api/signals` (staged `:231`). The authorized mechanical repair on that
      corpus is a **PREDICATE — every `ingest_signal(` call site missing the required `received_at=`
      kwarg** (live count 8, not the 6 originally written; do not encode a number) — plus the
      `SIGNAL_REPLAYED` import path fix (`app.store.core:5587`).
      — TRACED(repo-wide grep: absent; M4b F-12; `SIGNAL-R5b1-NEEDS-INPUT-DISPOSITION.md` D1/D2/D5).

- [x] **D-R5b2-18 ✅ RATIFIED 2026-07-25 (Ameen): MUTATION-FREE READS — lazy reads vs `SIGNAL_EXPIRED`
      (event-log truth).**
      Accepted `02-lifecycle.md:47` defines `SIGNAL_EXPIRED` as emitted by "sweep, **lazy-expiry**, or
      dead-on-arrival at ingest" with an accepted payload value **`detected_by: "read"`**, and `:97`
      says "TTL lapse … EXPIRED (**lazy** + sweep, rule A4)". The staged corpus asserts the opposite:
      `test_list_signals_lazy_expiry_does_not_mutate_store` (`:112`). **A read that appends a durable
      event is an event-log-truth question on a human-gated surface — it is not the implementer's
      call.** Planning-seat recommendation: **mutation-free reads** — reclassify via a pure
      `effective_signal_status(record, now)`; the durable `SIGNAL_EXPIRED` comes from the sweep, from
      ingest (dead-on-arrival), or atomically inside the A-2 conversion command. Rationale:
      single-writer discipline (a producer-facing GET must not become a writer); write amplification on
      a hostile-input surface; `effective_signal_status` is already the designed derivation; and rule
      A3 holds either way because conversion re-checks TTL atomically.
      **RATIFIED OUTCOME (operator, 2026-07-25): mutation-free reads.** Reads reclassify via a pure
      `effective_signal_status(record, now)` and append **nothing**; the durable `SIGNAL_EXPIRED` is
      written by the sweep, at ingest (dead-on-arrival, `detected_by:"ingest"`), or atomically inside
      the A-2 conversion command. The staged pin
      `test_list_signals_lazy_expiry_does_not_mutate_store` is therefore **correct and load-bearing** —
      never weaken it.
      **Required amendment shipping WITH this rung:** `docs/spec/signal-seat/02-lifecycle.md` — state
      that lazy expiry is **projection-level reclassification**, and remove `"read"` from
      `detected_by` (or redefine it as sweep-attributed). This is an **event-log-truth change on a
      human-gated surface**: it ships in the same change, is called out explicitly in the REV-0043
      request, and the reviewer verifies the amended text against the implementation. Do **not** ship
      the code without the amendment, or the spec and behavior diverge silently.
      — TRACED(`02-lifecycle.md:47,97`; staged `test_signal_facade_reads.py:112`; disposition D5;
      operator ratification 2026-07-25).

- [x] **D-R5b2-17 Matrix lives in its OWN test module — a planning-seat reoptimization.**
      `tests/test_signal_routes.py` is the shared target of R5b-1, R5b-2, R6 **and** R7; four rungs
      editing one file guarantees collisions. Put the authorization matrix and its `REQUIRED`/
      `CLASSIFIED` constants in a **new dedicated module** (e.g.
      `tests/test_route_authorization_matrix.py`) so R6/R7 extend a small focused file instead of
      merging into the large one. The crown-jewel audit test (D-R5b2-11) stays with the signal-route
      corpus. — TRACED(M4b H-6).

## Step-0 report

Verified against `fa087deb56bc58fa627e26a54de6e1bc39a27169` after the hard gate and before any
production or test edit:

1. **Producer route:** `POST /api/signals`; the router prefix and decorator are
   `app/api/routes_signals.py:34,203`, and `app/main.py:198-199` mounts it only when the flag is on.
2. **Facade reads:** R5b-1 did not author `list_signals` or `get_signal`;
   `StoreBackedSignalFacade` implements only `ingest_signal`.
3. **Actor dependency:** `get_actor` is byte/text-equal across pre-R5b-1, R5b-1, and current master.
4. **Credential helpers:** `operator_key_valid` exists; `producer_key_valid` does not. Producer
   matching remains inside `resolve_producer_id`.
5. **Auto-docs:** R5b-1 did not disable them; all four default endpoints are mounted.
6. **Facade exports:** `SignalCommandFacade`, `SignalIngestOutcome`, `SignalIngestResult`, and
   `StoreBackedSignalFacade`; there is no archive-style `SignalFacade`.
7. **Mounted operations:** recursive discovery found 35 `/api` operations; `app.openapi()` found
   the same exact set; four auto-doc endpoints bring the canonical total to 39.

**Divergence flagged:** `flag_on_settings()` does not explicitly pin `enable_dev_routes=True`.
The built `Settings` currently resolves it to `True` from the class default, so the measured set
still contains `POST /api/dev/candidates`. Matrix bounds must derive from the built settings and
condition the row on `settings.enable_dev_routes`; they must not rely on the inaccurate wording.

The actor-consumer re-grep also confirmed 14 `Depends(get_actor)` declarations plus the two direct
required `X-Actor` headers, and exactly 16 `command_facade.*` calls.

## Slice scoreboard

| Slice | Status | Evidence |
|---|---|---|
| Hard gate / branch | GREEN | Clean tree; origin fetched; producer route blob and REV-0042 disposition present; branch from `origin/master`. |
| Step 0 | GREEN | Seven findings re-derived; 35 API + 4 docs = 39; one non-blocking helper-wording divergence recorded. |
| Activation / continuity | GREEN | Active WO + state file ready; decision block copy verified exact (17,372 characters). |
| Staged corpus adaptation | PENDING | — |
| Operator middleware + principal | PENDING | — |
| Actor migration / dual-store | PENDING | — |
| Signal read facade + route | PENDING | — |
| Authorization matrix + docs/root-path | PENDING | — |
| Cockpit + environment docs | PENDING | — |
| Lifecycle amendment | PENDING | — |
| Full gate battery | PENDING | — |
| REV-0043 staging / push | PENDING | — |

## Evidence log

### 2026-07-25 — setup, hard gate, and Step 0

```yaml
- evidence:
    command: "git status --short"
    result: PASS
    decisive_output: "empty output"
- evidence:
    command: "git fetch origin"
    result: PASS
    decisive_output: "exit 0"
- evidence:
    command: "git ls-tree master app/api/routes_signals.py"
    result: PASS
    decisive_output: "100644 blob 0fe0ed03cafd171145866bce90b6f2367d0995eb app/api/routes_signals.py"
- evidence:
    command: "Test-Path work/review/REV-0042/disposition.md"
    result: PASS
    decisive_output: "present; 3032 bytes"
- evidence:
    command: "git checkout -b codex/signal-r5b2-operator-auth origin/master"
    result: PASS
    decisive_output: "branch created and tracking origin/master at fa087deb"
- evidence:
    command: "git fetch origin codex/signal-tests-staging archive/claude-wo-0001-install-checks-2x5ys8"
    result: PASS
    decisive_output: "both named refs fetched"
- evidence:
    command: "recursive flag-on route inventory + app.openapi() cross-check"
    result: PASS
    decisive_output: "35 /api operations; exact OpenAPI equality; 4 auto-doc endpoints; total 39"
- evidence:
    command: "source/blame comparison for Step-0 items 1-6 and actor-consumer grep"
    result: PASS
    decisive_output: "POST-only producer route; facade reads absent; get_actor unchanged; operator helper only; docs enabled; exports verified; 14 + 2 actor routes"
```
