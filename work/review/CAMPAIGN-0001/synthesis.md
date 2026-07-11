# CAMPAIGN-0001 — Interim Synthesis: Is the Wave-1 Spine Solid?

**Scope:** Wave 1 (the safety-critical spine) — REV-0004 ATTACK-CHAIN, REV-0005 ENGINE,
REV-0006 STORE-SPEC, REV-0007 EVENTS, REV-0008 ARCH.
**Frozen base:** `b600101` (== HEAD `app/`, byte-identical). **Verification env:** Python 3.12.3
venv with full gate tooling (`pytest`/`ruff`/`mypy`/`import-linter`/`grimp`).
**Method:** every Codex finding independently re-derived + reproduced in 3.12 (the env Codex lacked —
it had only 3.14 and no gate tools), then judged CONFIRMED / PARTIAL / REFUTED / NEEDS-HUMAN against
the invariant **statements** (not the pinning tests).

## Headline verdict

**The Wave-1 spine is composition-solid on every safety-critical guarantee — NO live P0 survived
verification.** All three P0-candidates resolved down: the flagship crash-window double-submit is
**REFUTED** (adapter `client_order_id` idempotency), the kill-switch/HALTED intent is **P1** (the
claim gate still blocks the venue order), and the sqlite flatten atomicity is a **P1 human decision
gap** (documented recover-forward vs the invariant text), not an unguarded corruption.

The deepest guards all held under adversarial probing: **single-writer** discipline, the
**claim-gate** kill re-check (INV-021/060), **write-path transition guards** (INV-075), and
**adapter-level idempotency** (ADR-002). What the review *did* surface is real and worth fixing —
audit-trail gaps on gated surfaces, one genuine invariant-vs-code decision gap, and forward-hardening
of a contract — but none of it is an exploitable safety hole at the frozen base.

## Verified findings (reviewer severity → verified severity)

| ID | Packet | Reviewer | **Verified** | Verdict | One-line |
|---|---|---|---|---|---|
| UC-001 | REV-0004 | P0? | **—** | **REFUTED** | Redrive re-submits under stable `client_order_id`; real adapter recovers the duplicate (1 venue order). Contract/beta-preflight note only. |
| ENG-001 | REV-0005 | P0 | **P1** | CONFIRMED | Protection intent+order created under HALTED (real concurrent-kill TOCTOU) — but claim gate blocks the venue order; harm is intent/audit + a stranded `CREATED` order. |
| REV-0006-F-001 | REV-0006 | P0 | **P1** | CONFIRMED / **NEEDS-HUMAN** | sqlite `flatten_position` = 4 transactions; hard-crash strands an approved-no-order intent (memory is atomic). True INV-050-*statement* violation + interim protection gap; code documents recover-forward. |
| UC-002 | REV-0004 | P1 | **P1** | CONFIRMED | Operator `actor` dropped on cancel audit event (both stores); F-002 class not extended to cancel. |
| REV-0007-F001 | REV-0007 | P1 | **P2** | PARTIAL | Runtime parity omits order-status — but it's the disclosed deferral, not an ADR-004 required test, compensated by a scripted parity test; divergence single-writer-unreachable. |
| REV-0007-F002 | REV-0007 | P1 | **P2** | PARTIAL (reach. REFUTED) | Fold has no terminality guard — but `append_execution_event` has zero production callers; write-path planners reject malformed/illegal events. INV-075 guards it. |
| ARCH-001 | REV-0008 | P1 | **P2** | CONFIRMED | Contract-5 bypassable via new route / `get_store` DI (real `lint-imports` proof) — but **latent**, no current route does it. Forward-hardening. |
| ENG-002 | REV-0005 | P2 | **P2** | CONFIRMED | Timeout-quarantine venue queries not under the loop budget (read-only; low impact). |
| REV-0006-F-002 | REV-0006 | P2 | **P2** | CONFIRMED | Planners raise bare `ValueError` (→422) vs ABC-promised `OrderTransitionError` (→409); client-unreachable. |
| ARCH-002 | REV-0008 | P2 | **P2** | CONFIRMED | Stale facade module docstrings claim P1-only surface; no real protocol drift. |

**Net:** 0 live P0 · 3 P1 (2 fix-now + 1 human decision) · 5 P2 · 1 REFUTED. Zero findings REFUTED
on their *mechanics* — Codex's factual claims were almost all accurate; the corrections are to
**severity and reachability**, which is exactly what the supported-env re-run exists to establish.

## Foundation-health scorecard (container-group × lens)

| Group | Container | Health | Notes |
|---|---|---|---|
| G-E Engine | monitoring.py + reconciliation.py | **Amber** | Kill-switch TOCTOU at intent layer (ENG-001 P1); budget gap (P2). Venue-safety intact. |
| G-B Store spec | base.py + core.py | **Amber** | sqlite flatten atomicity decision gap (F-001 P1/NEEDS-HUMAN); error-contract nit (P2). |
| G-D Events | projectors.py + replay.py | **Green‑ish** | No production-reachable defect; parity + write-path guards hold. Hardening + doc-accuracy only. |
| G-I/facade seam | store_backed.py, api, deps | **Amber** | Actor dropped on cancel (UC-002 P1); Contract-5 latent bypass (ARCH-001 P2). |
| Arch (holistic) | .importlinter + seams | **Green (today) / Amber (forward)** | Structure matches target now; contract incomplete against future routes. |
| Cross-container | attack chains | **Green** | Flagship double-submit refuted; kill/quarantine/single-writer chains held end-to-end. |

## Prioritized remediation roadmap

**All remediations touch human-gated surfaces → each is a fresh gated WO: human-approved → Claude
authors test-first → Codex independent re-review (the REV-0001/2/3 loop). None auto-applied.**

**Tier 1 — fix before the spine is declared beta-ready (2 fix-now + 1 decision):**
1. **F-001 decision (NEEDS-HUMAN first):** choose **(A)** bless recover-forward — amend INV-050's
   statement + close the `monitoring.py:338` orphan-active-intent protection gap — or **(B)** make
   sqlite `flatten_position` a single transaction to match memory + INV-050. Either way the interim
   protection gap must close. (manual-flatten + invariant/ADR surface)
2. **ENG-001 (P1):** re-read trading-state per symbol immediately before the protection intent
   mutation (or serialize the halted-check with intent creation atomically); regression covering the
   concurrent-kill-during-await interleaving, both stores. (kill-switch surface)
3. **UC-002 (P1):** thread `actor` through `transition_order` / `plan_transition_order` (schema-
   touching) so cancel audit events carry operator identity; dual-store route-level coverage.
   (cancel/replace surface)

**Tier 2 — hardening + doc-accuracy (batch):**
4. **ARCH-001 (P2):** close the Contract-5 completeness gap (enumerate routes / forbid `get_store` to
   routes) + regression proving both bypasses fail.
5. **REV-0007-F001 (P2):** add an order-status projection to the runtime dual-store read-model parity
   verifier; refresh the stale scope-note.
6. **REV-0007-F002 (P2):** correct ADR-008 / INV-075 wording (transition bound is the *write path*,
   not the fold); optional append-boundary validation as defense-in-depth.
7. **ENG-002 / REV-0006-F-002 / ARCH-002 (P2):** budget-thread the quarantine resolver; align the
   error-type contract; refresh the facade module docstrings.

**Beta pre-flight (not a code change):** confirm with the live Alpaca paper venue that a duplicate
`client_order_id` is rejected for **all** order states incl. post-fill (the one external assumption
UC-001's safety rests on).

## Completeness note
Every Wave-1 finding has a CONFIRMED/PARTIAL/REFUTED/NEEDS-HUMAN verdict with a 3.12 repro or a
statement-level analysis. No in-scope container was left with neither a finding nor a null-result
probe. Codex's own null-result logs (clean fill-cascade, self-heal, claim-gate projection, dedup,
snapshot/replay, cockpit↛app, SDK confinement, no store↔events cycle) were spot-confirmed and are
recorded as positive coverage. **Wave 1 gate: interim PASS with a Tier-1 remediation set + one human
decision outstanding** before G-E/G-B clear.

---

# Wave 2 scorecard (REV-0009…0014)

Six container deep-dives (STORE-IMPL, KERNEL, BROKER, MARKETDATA, FACADE-API, STRATEGY), reviewed by
Codex at frozen base `b600101` on Python 3.12.3, then **each finding + every ACCEPT re-verified by an
internal adversarial completeness pass** (the synthesis's job: an ACCEPT is not a free pass — a
container with no finding gets a completeness probe). Two real defects the ACCEPTs **missed** were
recovered this way.

| REV | Container | Codex verdict | After verification | Gate |
|---|---|---|---|---|
| 0009 | STORE-IMPL | ACCEPT-WITH-CHANGES | Only REV-0006-F-001 (already fixed `27bbffb`, REV-0019-cleared); no other parity divergence | **CLEARS** |
| 0010 | KERNEL | ACCEPT | NaN→risk gate **REFUTED** (all ingress gated); +W2-RISK P3 hardening note | **CLEARS** |
| 0011 | BROKER | ACCEPT | UC-001-refuted class **CONFIRMED** (client_order_id idempotency); beta pre-flight carried | **CLEARS** |
| 0012 | MARKETDATA | ACCEPT | **OVERRIDDEN → INCOMPLETE.** W2-STALE **P1** (feed-wide staleness) — Codex missed it | **DOES NOT CLEAR** |
| 0013 | FACADE-API | ACCEPT-WITH-CHANGES | W2-CAND **P1** confirmed; W2-SESS **P2** (Codex missed); raw-500 **REFUTED** (reachable) | **DOES NOT CLEAR** |
| 0014 | STRATEGY | ACCEPT-WITH-CHANGES | W2-CAND **P1** confirmed (shared root); evaluate determinism/NaN clean | **DOES NOT CLEAR** |

**Net new confirmed findings:** 2 × P1, 1 × P2, 1 × P3.
- **W2-CAND (P1)** — candidate single-flight absent at the store boundary (REV-0013 + REV-0014, shared
  root): `create_candidate` inserts unconditionally in both stores; double-approval → two BUY order
  intents; reachable via strategy-loop TOCTOU + the beta-default-on dev route. Sell side is the
  correct-pattern oracle.
- **W2-STALE (P1)** — market-data staleness is **feed-wide, not per-symbol**: a quiet held symbol's
  stale price passes the protective-floor gate (both directions — masked breach + spurious exit). Live
  in the beta config (real `AlpacaMarketDataStream`; the fake feed doesn't model it — why tests + the
  review missed it). Touches the protection safety surface.
- **W2-SESS (P2)** — session-close drops the operator actor (same class as Wave-1 UC-002); the audit
  can't attribute who closed the session. Additive fix.
- **W2-RISK (P3)** — `risk_limit_reason` is single-layer defense (no internal finite-check); optional
  defense-in-depth guard. Non-gating.

**Refuted / non-findings:** NaN→risk gate (latent, unreachable — gated upstream); reachable raw-500
(466 hostile requests, 0 × 5xx; latent missing-wrap on no-`try` read routes only).

**Meta / campaign-health:** the completeness critic recovered **two** confirmed defects (W2-STALE P1,
W2-SESS P2) that the independent reviewer's ACCEPT/ACCEPT-WITH-CHANGES did not surface — validating the
two-layer design (independent cross-model review **plus** an internal adversarial completeness pass on
every ACCEPT). Every Codex finding whose *mechanics* were stated held up; the adjustments were to
completeness and to severity/reachability, established in the supported 3.12 env.

## Wave-2 remediation roadmap (batched human decisions)
1. **W2-CAND (P1)** — store-authoritative active-candidate dedup in `create_candidate` (both stores,
   atomic with insert) mirroring `create_sell_intent`; collision semantics (return-existing vs 409);
   `base.py` contract clause; dual-store + double-approval regression. *(candidate/order state — not a
   hard-gated surface, but present diff for approval given it shapes BUY-intent flow.)*
2. **W2-STALE (P1)** — per-symbol freshness gate at the consumer/snapshot boundary, feed-wide clock
   kept as a separate connection-liveness signal; real-stream + multi-symbol regression. **Human
   decision on approach** (protective-floor safety surface).
3. **W2-SESS (P2)** — thread `actor` through `close_session` → event payload (UC-002 pattern; additive).
4. **W2-RISK (P3)** — optional finite-check hardening in `risk_limit_reason`.

**Wave-2 gate: 3 of 6 containers clear (STORE-IMPL, KERNEL, BROKER). MARKETDATA / FACADE-API / STRATEGY
hold on 2 P1 + 1 P2 remediations.** Combined with Wave 1: no live P0 across the spine; the open risk is
concentrated in the two new P1s (candidate single-flight, feed-wide staleness), both remediable without
touching the event-sourced core.
