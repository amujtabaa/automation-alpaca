---
type: Work State
work_order_id: WO-0139
status: REVIEW
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
    - "flag_on_settings explicitly pins enable_dev_routes=True; route bounds still derive from the built settings object."
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

**Historical divergence (resolved after REV-0043 F-3):** Step 0 found that
`flag_on_settings()` did not explicitly pin `enable_dev_routes=True`; the class default happened to
resolve it to `True`. The helper now pins the value. Matrix bounds continue to derive from the built
settings and condition the dev row on `settings.enable_dev_routes`.

The actor-consumer re-grep also confirmed 14 `Depends(get_actor)` declarations plus the two direct
required `X-Actor` headers, and exactly 16 `command_facade.*` calls.

## Slice scoreboard

| Slice | Status | Evidence |
|---|---|---|
| Hard gate / branch | GREEN | Clean tree; origin fetched; producer route blob and REV-0042 disposition present; branch from `origin/master`. |
| Step 0 | GREEN | Seven findings re-derived; 35 API + 4 docs = 39; one non-blocking helper-wording divergence recorded. |
| Activation / continuity | GREEN | Active WO + state file ready; decision block copy verified exact (17,372 characters). |
| Staged corpus adaptation | GREEN | Facade-read corpus mechanically repaired; route, matrix, and cockpit rows adapted to the current tree without copying stale production code. |
| Operator middleware + principal | GREEN | Targeted auth corpus RED on every named gap → GREEN as part of 218 passed. |
| Actor migration / dual-store | GREEN | Exact actor was RED as raw `desk-3` in 4/4 memory/SQLite cases → GREEN 4 passed as `operator:authenticated:desk-3`. |
| Signal read facade + route | GREEN | Facade RED 16 failed / 14 passed → GREEN 30 passed; combined HTTP/auth corpus GREEN 218 passed. |
| Authorization matrix + docs/root-path | GREEN | Literal existence + classification ratchet, exact OpenAPI set, derived count, role outcomes, absent docs, unmatched denial, and root-path regression all GREEN in 218 passed. |
| Cockpit + environment docs | GREEN | Header merge, case-insensitive env-key authority, caller-dict immutability, and critical-control/read seam GREEN; safe flag/key placeholders documented. |
| Lifecycle amendment | GREEN | Accepted text now defines mutation-free effective read projection and removes `detected_by:"read"` from durable event truth. |
| Full gate battery | GREEN | Static gates clean; focused 258; full 4,586 collected with exit 0; R2 61; scaling 13; bootstrap exit 0. |
| REV-0043 staging / push | GREEN | REV-0043 staged against `fa087deb..10d2bce`; delivery branch published to origin with no PR. |
| REV-0043 F-1/F-2 remediation | GREEN | F-1 weakening mutation failed the new `/fills` negative at 404 vs 422; F-2's natural RED reported lowercase `x-actor` for both routes, then GREEN with canonical `X-Actor`; recovery file 6 passed. |
| REV-0043 close-out items | REVIEW / NEEDS-INPUT | F-3 helper pin, F-5 ingest-echo clause, and F-7 PKL refresh applied. F-4 awaits the operator; F-6/F-8 are recorded for R6 only. |
| REV-0043 remediation gate battery | GREEN | Ruff/mypy/imports/PKL clean; focused 260; full 4,588 collected with exit 0; R2 61; scaling 13; bootstrap exit 0. |

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

### 2026-07-25 — facade read slice

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_facade_reads.py --basetemp <OS temp> -p no:cacheprovider"
    result: FAIL
    decisive_output: "RED: 16 failed, 14 passed; list_signals/get_signal and read clock absent; replay/conflict echoed stored RECEIVED"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_facade_reads.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "GREEN: 30 passed across memory and SQLite"
```

### 2026-07-25 — operator enforcement, route matrix, and cockpit slice

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_routes.py tests/test_route_authorization_matrix.py tests/test_cockpit_operator_header.py --basetemp <OS temp> -p no:cacheprovider --tb=no"
    result: FAIL
    decisive_output: "RED after 49 inherited cases: signal reads/auth, producer helper, principal-led audit actor, credential matrix, docs, unmatched path, root-path matching, and cockpit operator header were absent"
- evidence:
    command: "same targeted command after first implementation"
    result: FAIL
    decisive_output: "collection stopped: FastAPI 0.139 rejects Optional[Request] as a dependency response field"
- evidence:
    command: "same targeted command after dependency-signature repair"
    result: PASS
    decisive_output: "218 passed; only existing Starlette deprecation warnings"
```

### 2026-07-25 — recovery actor migration

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: FAIL
    decisive_output: "initial harness defect: get_execution_events has no order_id parameter; all 4 cases stopped before the intended assertion"
- evidence:
    command: "same targeted command after local stream filtering"
    result: FAIL
    decisive_output: "intended RED: 4 failed; both recovery routes persisted raw desk-3 on memory and SQLite"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "GREEN: 4 passed; exact operator:authenticated:desk-3 on both routes and stores"
```

### 2026-07-25 — independent corpus review and strengthening

```yaml
- evidence:
    command: "read-only failure-capability review of the R5b-2 corpus"
    result: FAIL
    decisive_output: "nine gaps: schema-hidden non-API ratchet, near-path exemptions, get/list read immutability and clocks, real flag-off request shape, unlabeled principal, valid filters, full-map key traversal, and cockpit key precedence"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_cockpit_operator_header.py --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: FAIL
    decisive_output: "intended RED: case-variant caller operator header survived beside the environment-owned credential"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_facade_reads.py tests/test_signal_routes.py tests/test_route_authorization_matrix.py tests/test_cockpit_operator_header.py tests/test_recovery_actor_provenance.py --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: FAIL
    decisive_output: "test repair required: missing PRODUCER_ID import; 257 cases passed before the one test NameError"
- evidence:
    command: "same strengthened focused-corpus command after repair"
    result: PASS
    decisive_output: "258 passed; only existing Starlette deprecation warnings"
```

### 2026-07-25 — first full-suite gate

```yaml
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q --basetemp <OS temp> -p no:cacheprovider"
    result: FAIL
    decisive_output: "one failure: inherited recovery-route test expected missing X-Actor to return 422 but migration returned 200"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_wo0114_pd1_release_valve.py::test_http_requires_actor_and_uses_typed_command_facade tests/test_recovery_actor_provenance.py tests/test_route_authorization_matrix.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "156 passed after preserving the required-label contract through a principal-preferring wrapper"
```

### 2026-07-25 — final gate battery and review staging

```yaml
- evidence:
    command: ".venv/Scripts/ruff.exe check ."
    result: PASS
    decisive_output: "All checks passed!"
- evidence:
    command: ".venv/Scripts/ruff.exe format --check <12 R5b-2-owned Python files>"
    result: PASS
    decisive_output: "12 files already formatted"
- evidence:
    command: ".venv/Scripts/mypy.exe app/"
    result: PASS
    decisive_output: "Success: no issues found in 77 source files"
- evidence:
    command: ".venv/Scripts/lint-imports.exe"
    result: PASS
    decisive_output: "Contracts: 6 kept, 0 broken"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q <five-file R5b-2 corpus> --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "258 passed on final implementation head"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "4,586 collected; exit 0 at 100%; 4,574 passed, 11 skipped, 1 expected xfail marker; 407 s"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/r2_conformance_oracle.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "61 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_wo0113_repair_scaling.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "13 passed"
- evidence:
    command: ".venv/Scripts/python.exe harness/bootstrap.py"
    result: PASS
    decisive_output: "exit 0; dependencies already satisfied; Ruff/mypy/collection completed; 4,586 tests collected"
    note: "restricted-network pip retries were non-fatal because dependencies were already satisfied"
- evidence:
    command: "final flag-on route inventory"
    result: PASS
    decisive_output: "36 mounted HTTP operations; exact OpenAPI equality; all four auto-doc paths absent; dev route enabled"
- evidence:
    command: "git diff --check"
    result: PASS
    decisive_output: "empty output"
- evidence:
    command: "git push -u origin codex/signal-r5b2-operator-auth"
    result: PASS
    decisive_output: "new remote branch created and upstream tracking configured; no PR created"
```

### 2026-07-25 — REV-0043 ACCEPT-WITH-CHANGES remediation

```yaml
- evidence:
    command: "git fetch origin claude/signal-r4-kickoff-planning-354qc0; git show e881f52:work/review/REV-0043/result.md"
    result: PASS
    decisive_output: "reviewer-owned result read at e881f52; verdict ACCEPT-WITH-CHANGES; artifact not copied to or edited on the delivery branch"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: PASS
    decisive_output: "pre-remediation baseline: 4 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py::test_flag_off_recovery_routes_require_canonical_x_actor_header --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: FAIL
    decisive_output: "F-2 RED: 2 failed; both routes returned ('header', 'x-actor') instead of ('header', 'X-Actor')"
- evidence:
    command: "temporary /fills-only Depends(get_required_actor) -> Depends(get_actor) mutation; run the fills parameter; restore immediately"
    result: FAIL
    decisive_output: "F-1 mutation RED: expected 422, got 404; the new negative detects loosened requiredness"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py::test_flag_off_recovery_routes_require_canonical_x_actor_header --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: PASS
    decisive_output: "F-1/F-2 GREEN after restoring requiredness and alias: 2 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_recovery_actor_provenance.py --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: PASS
    decisive_output: "6 passed, including both flag-off negatives and both dual-store provenance controls"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_route_authorization_matrix.py::test_required_routes_exist_and_every_discovered_route_is_classified --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: PASS
    decisive_output: "1 passed with enable_dev_routes explicitly pinned"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_signal_facade_reads.py -k '<two existing-record ingest echo tests>' --basetemp <OS temp> -p no:cacheprovider --tb=short"
    result: PASS
    decisive_output: "4 passed across memory and SQLite"
```

### 2026-07-25 — REV-0043 remediation final gate battery

```yaml
- evidence:
    command: ".venv/Scripts/ruff.exe check ."
    result: PASS
    decisive_output: "All checks passed!"
- evidence:
    command: ".venv/Scripts/ruff.exe format --check <13 R5b-2-owned Python files, including signal_seat_helpers.py>"
    result: PASS
    decisive_output: "13 files already formatted"
- evidence:
    command: ".venv/Scripts/mypy.exe app/"
    result: PASS
    decisive_output: "Success: no issues found in 77 source files"
- evidence:
    command: ".venv/Scripts/lint-imports.exe"
    result: PASS
    decisive_output: "Contracts: 6 kept, 0 broken"
- evidence:
    command: ".venv/Scripts/python.exe .ai-os/scripts/check_pkl.py pkl/"
    result: PASS
    decisive_output: "PKL CHECK PASSED"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q <five-file R5b-2 corpus> --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "260 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "4,588 collected; exit 0 at 100% in 410.9 s; 11 skipped and 1 expected xfail marker; no FAILED or ERROR"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/r2_conformance_oracle.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "61 passed"
- evidence:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_wo0113_repair_scaling.py --basetemp <OS temp> -p no:cacheprovider"
    result: PASS
    decisive_output: "13 passed"
- evidence:
    command: ".venv/Scripts/python.exe harness/bootstrap.py"
    result: PASS
    decisive_output: "exit 0; dependencies already satisfied; Ruff/mypy/collection completed; 4,588 tests collected"
    note: "restricted-network pip upgrade retries were non-fatal because the environment was already satisfied"
- evidence:
    command: "flag-off OpenAPI inspection for both recovery POST operations"
    result: PASS
    decisive_output: "both expose one required header named exactly X-Actor"
```

## FIX blocks

### FIX-R5B2-01 — missing mutation-free signal read projection

- **Defect class:** missing read-half implementation.
- **Root cause:** R5b-1 intentionally delivered an ingest-only facade; there was no effective-status
  function, query facade, injected read clock, or list/get implementation.
- **Impact:** the operator read route could not be authored, and replay/conflict responses could echo
  a stored RECEIVED status after the TTL elapsed.
- **Files:** `app/facade/signal_commands.py`, `app/facade/signals.py`,
  `tests/test_signal_facade_reads.py`.
- **Fix:** add a typed query facade, pure effective-status projection, injected read clock, list/get
  filtering, and effective status on echoed ingest outcomes. Reads copy records and append nothing.
- **Evidence:** RED `16 failed / 14 passed` → GREEN `30 passed`; both stores; event-list equality
  before/after lazy list reads.

### FIX-R5B2-02 — sensitive mounted operations lacked request-time role enforcement

- **Defect class:** missing authorization boundary and incomplete audit principal binding.
- **Root cause:** the prior rung authenticated only producer ingest inside its route; the mounted app
  had no deny-by-default operator boundary, no request principal, and auto-docs remained exposed.
- **Impact:** sensitive reads and commands did not require the operator credential, while audit
  attribution could still be derived from caller-controlled `X-Actor`.
- **Files:** `app/main.py`, `app/api/deps.py`, `app/api/routes_signals.py`,
  `cockpit/api_client.py`, `tests/test_signal_routes.py`,
  `tests/test_route_authorization_matrix.py`, `tests/test_cockpit_operator_header.py`.
- **Fix:** add exact method/path role classification, constant-time key helpers, flag-scoped
  deny-by-default middleware, a distinct authenticated principal, operator-only signal reads,
  absent docs, and cockpit header merging.
- **Evidence:** named-gap RED → GREEN `218 passed`, including literal route existence,
  discovered-subset classification, exact OpenAPI equality, all credential outcomes, unmatched
  denial, root-path matching, crown-jewel actor equality, and critical cockpit operations.

### FIX-R5B2-03 — dependency annotation incompatible with the installed FastAPI version

- **Defect class:** collection-time framework incompatibility.
- **Root cause:** the planned `Optional[Request]` dependency annotation is treated as a Pydantic
  response field by FastAPI 0.139, so route registration fails before tests collect.
- **Impact:** no application route could be exercised after the first auth implementation.
- **Files:** `app/api/deps.py`.
- **Fix:** retain the direct-call-compatible default but annotate it as `Request`, using an explicit
  typed `None` cast; request injection still supplies the real object in HTTP execution.
- **Evidence:** collection failure on the first GREEN attempt → `218 passed`.

### FIX-R5B2-04 — recovery truth routes bypassed the authenticated actor dependency

- **Defect class:** audit-provenance bypass on two event-writing commands.
- **Root cause:** both recovery endpoints declared `X-Actor` directly instead of using
  `Depends(get_actor)`.
- **Impact:** canonical fill and human reconciliation truth recorded a caller label without the
  authenticated operator principal.
- **Files:** `app/api/routes_trading.py`, `tests/test_recovery_actor_provenance.py`.
- **Fix:** migrate both routes to the common principal-preferring dependency; prove exact persisted
  attribution with a fresh app for each store and command.
- **Evidence:** intended RED `4 failed` with raw `desk-3` → GREEN `4 passed` with exact
  `operator:authenticated:desk-3`.

### FIX-R5B2-05 — initial authorization corpus was not failure-capable at nine boundaries

- **Defect class:** incomplete negative and mutation-control coverage.
- **Root cause:** the adapted corpus covered the primary examples but omitted schema-hidden
  non-API mounts, near-path controls, event equality for singular reads, list-clock injection,
  actual flag-off request shape, unlabeled principals, positive filters, full-map comparison, and
  case-insensitive cockpit precedence.
- **Impact:** several weakening mutations could pass while violating ratified exactness,
  mutation-free reads, principal distinction, or credential authority.
- **Files:** `tests/test_signal_facade_reads.py`, `tests/test_signal_routes.py`,
  `tests/test_route_authorization_matrix.py`, `tests/test_cockpit_operator_header.py`.
- **Fix:** add the missing independent assertions and extend mounted-operation discovery to every
  flattened HTTP operation.
- **Evidence:** read-only review found nine concrete gaps; strengthened focused corpus GREEN
  `258 passed`.

### FIX-R5B2-06 — cockpit could retain a case-variant caller operator credential

- **Defect class:** ambiguous credential precedence.
- **Root cause:** ordinary dictionary assignment replaced only an exactly cased
  `X-Operator-Key`, leaving a case-variant spelling beside the environment-owned value.
- **Impact:** downstream case-insensitive header normalization, rather than the cockpit seam, could
  decide which credential reached the backend.
- **Files:** `cockpit/api_client.py`, `tests/test_cockpit_operator_header.py`.
- **Fix:** when the environment key is present, copy caller headers, remove any case-insensitive
  operator-key spelling, then inject the canonical header without mutating the caller dictionary.
- **Evidence:** intended cockpit RED `1 failed / 6 passed` → included GREEN in `258 passed`.

### FIX-R5B2-07 — recovery actor migration made a required header optional flag-off

- **Defect class:** flag-off API compatibility regression.
- **Root cause:** the two recovery routes moved from a required direct `X-Actor` header to
  `get_actor`, whose established contract intentionally permits an omitted optional label.
- **Impact:** a flag-off request that previously failed validation with 422 reached an event-writing
  recovery command with the default actor.
- **Files:** `app/api/deps.py`, `app/api/routes_trading.py`.
- **Fix:** add a narrow `get_required_actor` dependency that retains FastAPI's required header
  validation and delegates all accepted labels to the same principal-preferring resolver; use it
  only on the two migrated recovery routes.
- **Evidence:** full suite exposed expected `422`, actual `200`; focused inherited + dual-store +
  matrix rerun GREEN `156 passed`.

### FIX-R5B2-08 — `/fills` required-actor contract lacked a flag-off negative pin

- **Defect class:** inert regression pin / missing negative coverage (REV-0043 F-1).
- **Root cause:** the inherited missing-`X-Actor` assertion exercised `/reconcile` only, while every
  `/fills` call supplied the header.
- **Impact:** the canonical-fill route's required actor label could be loosened without a test
  failure, allowing a flag-off request to reach an event-writing command with the default actor.
- **Files:** `tests/test_recovery_actor_provenance.py`.
- **Fix:** add a valid-body flag-off `/fills` request without `X-Actor` and require 422; keep the
  symmetric `/reconcile` case beside it.
- **Evidence:** a temporary `/fills`-only weakening mutation made the new test fail at 404 vs 422;
  after restoration, both route cases passed.

### FIX-R5B2-09 — required actor header alias drifted from canonical `X-Actor`

- **Defect class:** flag-off validation and OpenAPI contract regression (REV-0043 F-2).
- **Root cause:** the shared `get_required_actor` wrapper retained requiredness and minimum length
  but omitted the explicit alias that both master routes declared.
- **Impact:** both 422 locations and both OpenAPI parameter names changed from `X-Actor` to
  `x-actor`, contrary to D-R5b2-13's flag-off compatibility requirement.
- **Files:** `app/api/deps.py`, `tests/test_recovery_actor_provenance.py`.
- **Fix:** restore `alias="X-Actor"` and pin the exact 422 location for both recovery routes.
- **Evidence:** natural RED `2 failed` with `('header', 'x-actor')` → GREEN `2 passed` with
  `('header', 'X-Actor')`.

## Review handoff

- Frozen semantic base: `fa087deb56bc58fa627e26a54de6e1bc39a27169`.
- Frozen implementation head: `10d2bce1fc11591a1994b1be891fef231df52fb5`.
- Curated commits: activation `a748c01`, implementation `75e328a`, compatibility fix `10d2bce`.
- Review request: `work/review/REV-0043/request.md`.
- Reviewer result: `e881f52ec94e36833e1db4b19abe12c0f1641142` on
  `claude/signal-r4-kickoff-planning-354qc0`; verdict `ACCEPT-WITH-CHANGES`. The reviewer-owned
  `result.md` remains absent from and unmodified on this delivery branch.
- Feature flag remains OFF. No rails, producer release/read, signal conversion, schema/migration,
  PR, merge, ledger mutation, result copy, disposition, or completion move was created.
- GAP-01 and mounted-route GAP-02 are closed by this implementation. The deferred item is the
  distinct spec-04 required-present completeness obligation for the future R6/R7 routes.
- REV-0043 F-1/F-2 are remediated red-first; F-3/F-5/F-7 close-out updates are included.
- The complete remediation gate battery passed with 4,588 tests collected; the branch remains in
  REVIEW solely because the operator-gated F-4 decision is unresolved.
- **NEEDS-INPUT (F-4):** the operator must acknowledge `detected_by:"conversion"` or direct its
  reversion to `"sweep" | "ingest"` for R7 to add with the emitter. No choice was made here.
- **R6 carry-forward only:** F-6 records that the fixed principal and colon-composed label are not
  losslessly separable once producer principals exist; F-8 records that `list_signals` materializes
  the full filtered scope because effective status cannot be pushed into the current store query.

```yaml
fable_done:
  task: "WO-0139 Signal Seat R5b-2 operator enforcement"
  done_when_results:
    - "MET: literal existence and all-mounted-route classification ratchets pass"
    - "MET: exact role outcomes, absent docs, unmatched denial, and root-path behavior pass"
    - "MET: all 16 actor-consuming commands use principal-preferring attribution"
    - "MET: signal reads use injected mutation-free effective status"
    - "MET: cockpit credential merge and critical-operation usability pass"
    - "MET: lifecycle text and safe environment template match the implementation"
    - "MET: full gate battery passes with fresh evidence"
    - "MET: WO status REVIEW and REV-0043 request staged"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    flag_enabled: false
    rails_or_conversion_built: false
  status: REVIEW
```
