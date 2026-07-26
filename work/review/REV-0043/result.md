---
type: Review Result
rev_id: REV-0043
title: "WO-0139 — Signal Seat R5b-2 operator enforcement surface"
reviewer_seat: Claude (independent review seat; implementer was Codex)
review_head_sha: d540258
branch: codex/signal-r5b2-operator-auth
human_gated_surfaces: [operator-authorization, event-log-actor-truth, cockpit-credentials, event-log-vocabulary]
verdict: ACCEPT-WITH-CHANGES
reviewed: 2026-07-25
---

# REV-0043 — result

## Method

Two independent passes, both against the branch rather than the report:

1. **Review-seat direct** — fresh POSIX runs; **four control mutations** on the matrix and enforcement
   layer; structural verification of the actor migration, the principal form, and the ratified
   lifecycle amendment; flag-off route-table measurement; full-suite non-regression.
2. **Fresh-context adversarial pass** — a **26-mutation battery**, a raw-ASGI path-confusion probe
   (path traversal, encoded separators, double slashes, trailing slash, case variants, `root_path`
   divergence), a flag-off OpenAPI diff against master, and cockpit call-site mapping.

**Every finding that affects the verdict was reproduced by the review seat directly.** One
methodological note against myself: my first full-suite run reported "exit 0" from a detached wrapper
while pytest was only at 9%; I caught it, waited for the real process, and only then recorded the
result. The pass below is the genuine one.

Defensive assurance of the operator's own local paper-only application. Defect-level reporting only.
The feature flag remains OFF.

## Verdict

**ACCEPT-WITH-CHANGES.** The two properties this contract was rewritten around are sound. Two P2
defects must land in this range, and one item needs an explicit operator acknowledgement.

---

## The P0 from the war-game is genuinely closed

WO-0139 rev-1's matrix derived its required set *from discovery*, making it structurally incapable of
detecting an absent route — the inert-pin class at the scale of the matrix protecting every route.
rev-2 replaced it with two independent assertions over a literal set. **Verified by review-seat
mutation:**

| Mutation | Assertion | Result |
|---|---|---|
| Unmount a required router (`routes_review`) | `required <= discovered` | **FAILS** ✓ |
| Add an unclassified route (`GET /api/zz-…`) | `discovered <= classified` | **FAILS** ✓ |
| Restored | both | green ✓ |

`REQUIRED` / `CLASSIFIED` are literal `frozenset`s of hardcoded `(method, path)` tuples
(`tests/test_route_authorization_matrix.py:26-87`) with an explicit "never computed from the app"
comment, and the six path templates rev-1 got wrong are all correct. The bound is **derived** from the
built `Settings` with the dev row conditioned on `settings.enable_dev_routes` (`:192-195`), plus an
exact `openapi()` set-equality cross-check (`:196`). The adversarial pass independently measured the
flattener as non-vacuous: a naive `app.routes` walk finds **0** `/api` operations (9 `_IncludedRouter`
wrappers), the flattener finds **36**.

The adversarial pass also confirmed failure-capability on a wrong path template and on re-enabled
auto-docs, and its raw-ASGI probe found **every** path-confusion and `root_path` variant fails
**closed** (401): `/api/positions/../health`, `..%2fhealth`, `//api/health`, `/api//health`,
`/api/health;/positions`, `/api/health\t`, `/API/health`, `HEAD /api/health`, `/api/health/`, and
`root_path` divergence. Only exact `GET /api/health` returns 200.

## Findings

### F-1 (P2, CONFIRMED) — the `/fills` required-actor control has no regression pin (*inert regression pin*)

**Cause.** FIX-R5B2-07's control (`Depends(get_required_actor)`) is applied to **both** recovery routes
(`app/api/routes_trading.py:225,251`), but the only missing-`X-Actor`→422 assertion in the repo
(`tests/test_wo0114_pd1_release_valve.py:761-762`) posts to `/reconcile` only. **Review-seat verified:**
every `/fills` HTTP call in the suite (`test_recovery_actor_provenance.py:94`,
`test_wo0114_pd1_release_valve.py:788,793`) sends `X-Actor`. No negative case exists.

**Impact.** The required-label contract on `POST /api/order-recoveries/{recovery_id}/fills` — which
**ingests a canonical fill, invariant 9** — can be silently loosened with nothing noticing. The
adversarial mutation (that route only → `Depends(get_actor)`) leaves the **full suite green**, while the
symmetric mutation on `/reconcile` **is** caught — proving the asymmetry rather than inferring it.

**Fix.** One assertion: flag-off `POST …/fills` with no `X-Actor` → 422. Best placed in
`tests/test_recovery_actor_provenance.py` so the pin lives with the migration it protects.

This is precisely the defect class this review gate exists to catch, on the most audit-critical route in
the rung.

### F-2 (P2, CONFIRMED EMPIRICALLY) — the `X-Actor` alias was dropped, changing the flag-off contract

**Cause.** `app/api/deps.py:233` declares `x_actor: str = Header(..., min_length=1)` — **no
`alias="X-Actor"`**. Master declared `actor: str = Header(..., alias="X-Actor", min_length=1)` on both
routes (`routes_trading.py:220,246`, verified).

**Impact — reproduced by the review seat on a flag-off app:** the 422 body's `loc` is now
`('header', 'x-actor')` where master returned `('header', 'X-Actor')`, and the published OpenAPI
parameter name changes correspondingly (the adversarial pass's flag-off OpenAPI diff against master is
**exactly two lines**, both this rename). HTTP header matching is case-insensitive, so live callers
including the cockpit are unaffected — but this is an **observable flag-off contract change**, and
D-R5b2-13's byte-equivalence criterion is exactly what FIX-R5B2-07 claims to have restored. Nothing
pins either surface.

**Fix.** Restore `alias="X-Actor"` at `deps.py:233`, plus a pin on the 422 `loc` for both routes.

### F-3 (P3) — `flag_on_settings` does not pin `enable_dev_routes`

`tests/signal_seat_helpers.py:40-48` relies on the class default (`app/config.py:183`). D-R5b2-4 asserts
the helper "pins `enable_dev_routes=True`" — **it does not**, and Codex flagged this itself as a
divergence in its Step-0 report rather than absorbing it. If that default flips,
`POST /api/dev/candidates` drops out of both `REQUIRED` and `CLASSIFIED` and the matrix stays green with
silently reduced coverage. **Fix:** pin it in the helper, or `assert settings.enable_dev_routes` in the
matrix test. *(The WO's wording was mine and was inaccurate; the implementation is correct.)*

### F-4 (P3) — NEEDS OPERATOR ACKNOWLEDGEMENT: the amendment added a `detected_by` token

`docs/spec/signal-seat/02-lifecycle.md:51` now reads `detected_by: "sweep" | "ingest" | "conversion"`.
D-R5b2-18's ratified outcome authorized **removing** `"read"`; adding `"conversion"` is a new
**event-log payload vocabulary** value, which the WO's own stop conditions bar. Nothing emits it today
(`app/store/core.py` emits only `"ingest"`; `03-rails.md` uses `"sweep"`), and conversion is R7's.

**Reviewer's assessment, disclosed.** The token names semantics the operator *did* ratify — the D5
decision text states the durable event comes "from the sweep, at ingest (dead-on-arrival), or atomically
inside the A-2 conversion command." So this is a faithful encoding of the ratified decision rather than
a new design choice, and I flagged it approvingly in review discussion before weighing it against the
stop condition. It is nonetheless a vocabulary change on a human-gated surface. **Recommendation:**
operator acknowledges the token explicitly (cheapest, and it documents ratified semantics), or it reverts
to `"sweep" | "ingest"` and R7 adds `"conversion"` alongside its emitter. **Not a blocker either way —
but it must be an explicit decision, not an inherited one.**

### F-5 (P3) — amended text does not describe the ingest echo it changed

`app/facade/signals.py:99-105` applies `effective_signal_status` to the record returned by
`ingest_signal`, so 200-replay and 409-conflict echoes report projected status (pinned at
`tests/test_signal_facade_reads.py:131,156`). The amendment scopes projection to "`GET`/facade reads"
(`02-lifecycle.md:109`). Behaviour is defensible and mutation-pinned; the text is narrower than the code.
**Fix:** one clause extending projection to ingest echoes.

### F-6 (P3) — the principal is a constant, and the composed label is not losslessly separable

`app/api/deps.py:22` uses a fixed `"operator:authenticated"` rather than D-R5b2-11's suggested
`operator:<key-id>` form, and `get_actor` composes `f"{principal}:{label}"` (`:227`). Consequences: a
second operator key would be indistinguishable in the event log; a label containing `:` makes prefix
parsing ambiguous; and flag-off a caller could send `X-Actor: operator:authenticated` and produce an
event byte-identical to a flag-on authenticated one. Not reachable in the current posture
(`operator_api_key` is a single scalar; flag-off has no auth at all), but it erodes distinguishability
across a flag flip and once R6 adds producer principals. **Record for R6.**

### F-7 (P3) — PKL knowledge refresh outstanding at close-out

`pkl/architecture/signal-seat.md:103` still says "Facade reads, operator enforcement, and lazy expiry
remain R5b-2" and predates the mutation-free-read ratification. Per CLAUDE.md's close-out rule this
lands in the finishing commit. *(The branch correctly ships no ledger line, disposition, or completion
move while in REVIEW.)*

### F-8 (P4) — forward note for R6

`StoreBackedSignalFacade.list_signals` (`app/facade/signals.py:109-137`) must project before filtering,
so `GET /api/signals` materializes every stored signal in scope; neither the facade nor
`StateStore.list_signals` accepts a limit. Pre-existing store shape, bounded only by R6's rails. **Hand
to R6.**

---

## What holds

| Property | Verdict | Evidence |
|---|---|---|
| Matrix: existence + ratchet, literal set, derived bound, openapi cross-check | ✅ | Review-seat mutations both fail; flattener 0→36 |
| Exact `(method, path)` public **and** producer exemptions (not prefixes) | ✅ | The archive's `/api/signals` prefix bug does not recur; `GET /api/signals` is operator-only |
| 401 (none/unknown) vs 403 (valid wrong-role) across all 34 operator ops × 4 credential cases, fresh app per case | ✅ | No destructive command executed by the matrix |
| Unmatched paths denied by default; raw-ASGI path confusion fails closed | ✅ | 12 hostile variants all 401 |
| Auto-docs ABSENT under the flag, asserted, reconciled with the count | ✅ | Re-enabling them fails four separate assertions |
| **Both recovery routes migrated off the direct header** | ✅ | `routes_trading.py:225,251` → `get_required_actor` |
| **Principal distinguishable from the flag-off default** | ✅ | `"operator:authenticated"` vs `DEFAULT_ACTOR="operator"`; the archive trap avoided |
| `X-Actor` cannot override the principal; exact-equality pins, dual-store, app per store | ✅ | `test_recovery_actor_provenance.py` over `any_store` |
| All 16 actor-consuming routes on the principal-preferring path | ✅ | 14 `get_actor` + 2 `get_required_actor` = 16 = 16 `command_facade.*` sites; zero raw actor `Header` left |
| Flag-off `get_actor` returns a control-character `X-Actor` unchanged (sanitization scoped under the flag) | ✅ | `deps.py:225-229`; unconditional sanitization is caught |
| Cockpit MERGES `X-Operator-Key`, never replaces; caller dict not mutated | ✅ | `api_client.py:28-38`; replace and no-key both caught |
| **No operator lockout** — all 29 cockpit call sites map into CLASSIFIED | ✅ | GAP-01 closed |
| Cockpit does not import `app.config`; env name hardcoded | ✅ | contract 2 KEPT |
| D5 amendment: projection-level reclassification, `"read"` removed, confined to the lazy-expiry change | ✅ | 4 hunks, all EXPIRED/lazy-expiry; ADRs, INVARIANTS, store, models untouched |
| Reads append nothing (both stores) | ✅ | Identity-`effective_signal_status`, ignored clock, and read-appends-event all caught |
| Scope discipline — no rails, release, `/api/producers`, approve/reject, conversion, schema | ✅ | `.importlinter` unchanged; contract 5 not re-added; ledger untouched |
| No existing test edited or weakened | ✅ | Only `test_signal_routes.py` touched, as a pure append |
| Static gates | ✅ | ruff clean · mypy **77 files** · lint-imports **6 kept / 0 broken** |
| R5b-2 corpus | ✅ | **264 passed** (review seat), 0 failures |
| **Full suite non-regression** | ✅ | **100%, zero `FAILED`/`ERROR`** (review seat, verified to completion) |
| Flag-off byte-equivalence (route surface) | ✅ | 34 `/api` paths, `/api/signals` absent — matches baseline |

**FIX-R5B2-05's claim is substantiated.** Codex reported finding and repairing nine
non-failure-capable boundaries in its own authorization corpus. The adversarial battery confirms all
nine are now mutation-sensitive — including the two strongest
(`test_producer_credential_helpers_visit_the_complete_key_map` catching a `producer_key_valid`
early-return, and `test_get_actor_flag_off_preserves_internal_control_characters` catching a
sanitization leak). Self-reported test-strengthening is exactly the claim most needing external
verification; it held. **24 of 26 mutations caught; the 2 survivors are F-1's two variants.**

## Required before ACCEPT

1. **F-1** — one assertion: flag-off `POST …/fills` with no `X-Actor` → 422. **Blocking-in-range.**
2. **F-2** — restore `alias="X-Actor"` at `deps.py:233` + pin the 422 `loc` on both routes.
3. **F-4** — **operator decision** on the `"conversion"` token (acknowledge, or revert and let R7 add it
   with its emitter).
4. **F-3, F-5, F-7** — ship with the close-out (helper pin, one amendment clause, PKL refresh).
5. **F-6, F-8** — carried to the R6 register; no action in this rung.

Re-review will be scoped to F-1, F-2, and the F-4 disposition — not a full re-run.
