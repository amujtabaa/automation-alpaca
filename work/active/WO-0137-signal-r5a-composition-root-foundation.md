---
type: Work Order
title: "Signal Seat R5a — composition-root foundation (config + create_app construction guards + launcher trio + rails seam)"
status: REVIEW
work_order_id: WO-0137
wave: signal-seat reconciliation ladder, step R5 (split; R5a = construction-time foundation)
model_tier: strong (LOCAL Codex — human-gated auth/launcher/transport security boundary)
risk: high
owner: Ameen / implementer: Codex local session
created: 2026-07-22
war_gamed: ".ai-os/core/18 FULL — grounding + M1–M3 + M4a + M4b COMPLETE; 10/11 claims hold, 0 safety refuted, 3 tracing defects fixed; ratifiable"
gated_surface: auth/launcher/transport bind — the localhost security boundary (D-HOST-1). Human-gated. NO schema/migration (config + launcher only) → NO mid-session DDL gate. Ends at status REVIEW with REV-0041 staged for the Claude seat.
---

# Work Order: Signal Seat R5a — composition-root foundation

> **HUMAN-GATED (auth/launcher/transport security boundary).** R5a builds the construction-time
> bind guard that is the load-bearing localhost security boundary (D-HOST-1). It ends at
> `status: REVIEW`, never self-closes, and stages `work/review/REV-0041/request.md` for the
> **Claude seat** (fresh code-review packet; REV-0027's certified-properties list + F-1/F-2/F-3 as
> the checklist — archive-ref, id-collision-renumbered). No ledger close-out line until the
> disposition lands.

> **The R5a / R5b boundary (construction-time vs request-time).** R5a owns everything that makes
> `create_app` refuse to **construct** under a bad/absent config: the full signal `Settings` +
> `validate_signal_seat_settings`, the three construction guards (launch-capability, credential-
> presence, rails-presence), the launcher trio, the `facade/signal_rails` Protocol seam, the
> conditional module-level `app`. **R5b (future WO-0138)** owns everything that makes a **request**
> fail auth: the operator-enforcement middleware, `routes_signals`, `deps`, `schemas`,
> `facade/signals`, docs-disable, cockpit plumbing, the route matrix. They **share** `app/main.py::
> create_app` (R5a lands the skeleton; R5b extends it) and `app/config.py` (R5a owns it wholesale;
> R5b consumes the cred fields) — sequential, so serialize R5a→R5b. Safe in between: the flag stays
> OFF until the joint D-2a milestone (GAP-03), so R5a's flag-on paths are exercised only by tests.

## Scope (M3-derived — the construction-time foundation)

`app/config.py` (all signal `Settings` fields + `validate_signal_seat_settings` + overlap helper);
the launcher trio `app/server.py` + `app/launch_guard.py` + `app/__main__.py`; the `app/main.py::
create_app` **skeleton** (signature + the three construction guards + the conditional module-level
`app`); the `app/facade/signal_rails.py` Protocol seam (`RailsDecision`, `is_conforming_rails`);
`tests/signal_seat_helpers.py`; the `README.md` launch correction; and the R5a-owned RED test
slices. **Not R5a:** `routes_signals`, `deps`, `schemas`, `facade/signals`, the operator-enforcement
middleware, docs-disable, cockpit, `.importlinter` (all R5b).

## M1 — Assumption ledger / decision block (every line TRACED or INHERITED; no ASSUMED pre-checked)

- [x] **D-R5a-1 Branch & corpus.** Branch `codex/signal-r5a-foundation` from current master; pull the
      R5a-owned test files from `origin/codex/signal-tests-staging`
      (`test_signal_seat_config.py`, `test_signal_seat_launcher.py`, `test_signal_seat_launch_guard.py`,
      `signal_seat_helpers.py`, and the `test_import_boundaries.py` `_SANCTIONED_*` hunk).
      — INHERITED(R4 branch/corpus convention) · TRACED(slice map @ WO-0128 on staging).
- [x] **D-R5a-2 Scope = construction-time foundation** (the split above). — TRACED(M3 boundary:
      `test_signal_seat_launch_guard.py:40-48 @ staging` requires the credential-presence guard,
      which requires the cred config → the config test spans transport+creds → R5a owns config +
      all three construction guards).
- [x] **D-R5a-3 Transport = `loopback` | `tailnet_serve`, Funnel/public forbidden.** Implement
      `SIGNAL_TRANSPORT_POLICIES = {"loopback","tailnet_serve"}`; **re-baseline** the staged config
      test's `tls_proxy` literal → `tailnet_serve` (authorized reconciliation to the accepted ADR,
      NOT test-weakening). — TRACED(accepted `docs/adr/ADR-009-signal-seat-boundary.md` A-1 +
      `docs/spec/signal-seat/04-auth-and-api.md:10-13` + D-SIG-3 + plan §6 "re-baseline against the
      amended ADR"). Operator confirmed (Finding A, 2026-07-22).
- [x] **D-R5a-4 Three construction guards, in order.** Under `signal_seat_enabled`, `create_app`
      raises `RuntimeError` on: (1) missing/forged launch capability (`is_sanctioned` False);
      (2) invalid config via `validate_signal_seat_settings` (blank/absent `operator_api_key`,
      empty/invalid producer map, operator≡producer role collision, transport ∉ policy set, budget
      ∉ [1,1000], TTL > 86400); (3) non-conforming rails (`is_conforming_rails` False). Error
      messages MUST carry the tokens the staged regexes match — in particular the TTL-out-of-range
      message must contain `A-3` (the field name `signal_server_max_ttl_seconds` is lowercase and
      would not match a bare `TTL`; the staged regex is `budget|TTL|A-3|A-4`,
      `test_signal_seat_launch_guard.py:150-174 @ staging`). — TRACED(archive `app/main.py:120-148`
      + `test_signal_seat_launch_guard.py:25-69 @ staging` + spec 04 §1).
      **BUILD HAZARD (M4b):** the R5a `create_app` skeleton EXCLUDES the archive's R5b module-level
      imports — `routes_signals` (`app/main.py:57 @ archive`) and the `app.api.deps` helpers
      (`DEFAULT_ACTOR`, `OPERATOR_KEY_HEADER`, `PRODUCER_KEY_HEADER`, `operator_key_valid`,
      `producer_key_valid`, `app/main.py:60-66 @ archive`) — and the two operator/producer
      middleware blocks. A verbatim port would `ImportError` (those R5b files are absent on master);
      the skeleton constructs flag-on with master's EXISTING routers and NO signal middleware.
- [x] **D-R5a-5 Conditional module-level `app` (the un-mintable serve edge).** Flag OFF → `app =
      create_app()` defined (bare uvicorn works, beta unchanged). Flag ON → `app` **NEVER assigned**
      (not even `None` — `None` is provably insufficient), so `uvicorn app.main:app` raises
      `ImportFromStringError` in `Config.load()` **before any socket binds**. — TRACED(archive
      `app/main.py:319-339` + the subprocess pin `test_signal_seat_launcher.py:153-198 @ staging`
      asserting no-listener + `'Attribute "app" not found'`). The `'Attribute "app" not found'`
      string is uvicorn's `ImportFromStringError` text under the pinned `uvicorn==0.51.0`
      (`constraints.txt:101 @ master`, M4b-verified) — a future uvicorn bump changing that text
      would break the staged pin independent of R5a's code.
- [x] **D-R5a-6 Bind guard = loopback-only, policy-name-agnostic.** `validate_transport_bind`
      returns `None` for a loopback host or a UDS, else the A-1 failure string (`"A-1"`,
      `"proxy-private"`, `"non-loopback"`); BOTH `loopback` and `tailnet_serve` bind loopback (the
      policy value gates the negative test + docs, not the bind). — TRACED(archive
      `app/launch_guard.py:53-73` + spec 04:13-17 + `test_signal_seat_launcher.py:39-68 @ staging`).
- [x] **D-R5a-7 Capability = code-owned only.** The mint sentinel never leaves `app/launch_guard.py`;
      the capability is NOT env/config/importable; `is_sanctioned(object())` and `is_sanctioned(None)`
      are False; the mint re-validates the bind (bind-bound). — TRACED(archive
      `app/launch_guard.py:42,76-132` + `test_signal_seat_launch_guard.py:51-91 @ staging`).
- [x] **D-R5a-8 Rails SEAM only, not the provider.** R5a lands `app/facade/signal_rails.py`
      (Protocol + `is_conforming_rails`) and the create_app rails-presence guard; the REAL rails
      provider is **R6 (WO-0104)**. The launcher positive-control test EXPECTS the rails
      `RuntimeError` (loopback passes the bind, then fails downstream on absent rails). — TRACED(
      plan §5 api-facade "signal_rails.py KEEP … inert until WO-0104 provider" +
      `test_signal_seat_launcher.py:97-105 @ staging`).
- [x] **D-R5a-9 REV citations → archive-ref provenance.** Renumber every archive `REV-0024`/`REV-0025`
      citation in `launch_guard.py`/`server.py`/`main.py` to
      `archive REV-00xx @ origin/archive/claude-wo-0001-install-checks-2x5ys8` (master's REV-0024 is
      a different packet). — TRACED(plan §2 id-collision rule).
- [x] **D-R5a-10 Import-boundary hunk lands in the SAME change** as `server.py`/`__main__.py`: the
      `test_import_boundaries.py` `_SANCTIONED_ALPACA_REACHERS` additions (`app.server`,
      `app.__main__`) — CI fails otherwise. R5a does NOT touch `.importlinter` (the `routes_signals`
      contract-5 line is R5b's). — TRACED(staged hunk `test_import_boundaries.py:45-54 @ staging` +
      plan §5 REWRITE-hunk-only).
- [x] **D-R5a-11 Flag stays OFF (D-2a).** R5a never enables the seat; the flag flips only at the
      joint R5+R6+R7 D-2a milestone. R5a-alone with flag-off is byte-equivalent to today's posture.
      — INHERITED(D-2a joint enablement; GAP-03 of the threat model) · TRACED(spec 04 + threat model
      `docs/THREAT_MODEL_SIGNAL_SEAT.md` GAP-03).

**No mid-session GATE:** R5a has no schema/migration and every decision above is TRACED/INHERITED —
it is fully pre-ratifiable. (Contrast R4's `signal_records` schema gate.) The only human gate is the
post-session REV-0041 code review.

## M2 — Capability lifecycle (every edge anchored; the enforcement edge is test-pinned)

- **Mint** — `mint_launch_capability(_MINT_TOKEN,…)`, token module-private, bind-revalidated
  (`launch_guard.py:42,94-127 @ archive`). Only `app/server.py::run` mints.
- **Construct** — `create_app(launch_capability=…)` → `is_sanctioned` → raise if absent under flag
  (`main.py:120-129 @ archive`).
- **Serve** — `uvicorn.run(app, host=loopback|uds)` after construction (`server.py:94-97 @ archive`).
- **Un-mintable edge (the guarantee)** — bare `uvicorn app.main:app`: module `app` undefined under
  flag → import fails pre-bind (`main.py:319-339 @ archive`). **Pinned** by
  `test_signal_seat_launcher.py:153-198 @ staging` (both `--lifespan` modes, socket-level proof).
- **Terminals** — `SystemExit(2)` on forbidden bind (`server.py:76-79`); `RuntimeError` on any failed
  construction guard (`main.py:120-148`); `ImportFromStringError` on bare-uvicorn. All anchored.

## M3 — Consumer inventory (control-action swept)

- **New readers** of the signal transport/cred config (`validate_transport_bind`,
  `mint_launch_capability`, `server.run`, `validate_signal_seat_settings`): all NEW in R5a; no
  existing master consumer reads a transport policy today (`app/config.py` has no signal fields). No
  existing consumer is affected by the additive fields. UCA sweep: the startup guard MUST fire before
  serve (server.py validates pre-serve) — pinned by the launcher subprocess test.
- **Affected existing consumer — the sole serve path:** the module-level `app = create_app()`
  (`app/main.py:168-169 @ master`), which R5a makes conditional on the flag. Bare
  `uvicorn app.main:app` appears as a doc/display string in `README.md:132` and
  `cockpit/app.py:941` (a Streamlit "start it first" warning — display only, no runtime break;
  cockpit is R5b scope, fixed there with the cockpit plumbing). **Bootstrap coupling (M4b-corrected
  — the original `harness/bootstrap.py:40` anchor was WRONG: that line is a Windows py-version
  probe, not a uvicorn call).** The real `bootstrap → app.main` path is the smoke gate's
  `pytest -q --collect-only` (`harness/bootstrap.py:117 @ master`), which imports the signal test
  modules → imports `app.main` **flag-OFF** → runs the module tail `app = create_app()`. That path
  is flag-off safe, so the non-regression holds. **Required verification:** R5a runs
  `python harness/bootstrap.py` and confirms the smoke gate stays green (the flag-off collect path),
  and lands the plan-mandated README correction ("app is None" → leave-name-UNDEFINED).
- **`create_app` callers:** signature gains `settings`/`launch_capability`/`signal_rails` (all
  defaulted None) → existing flag-off callers `create_app()` / `create_app(store)` unaffected;
  flag-on omission of the capability now correctly RAISES. Backward-compatible.

## Context packet (grounding map anchors — read before building)

- Accepted authority: `docs/adr/ADR-009-signal-seat-boundary.md` (A-1), `docs/spec/signal-seat/04-auth-and-api.md §1`.
- Archive design (REWRITE against master, cite archive-ref): `app/server.py`, `app/launch_guard.py`,
  `app/__main__.py`, `app/main.py` @ `origin/archive/claude-wo-0001-install-checks-2x5ys8` — read
  via `git show`. **Drift #2 (the load-bearing one):** master `create_app(store=None)`
  (`app/main.py:67 @ master`) has NO settings/capability/rails params, no guards, and an
  UNCONDITIONAL module-level `app` (`:168-169`) — this is a REWRITE of the signature + tail, not a
  clean diff apply.
- Staged RED corpus (green obligation): the three `test_signal_seat_*` files + `signal_seat_helpers.py`
  + the import hunk @ staging (map §3).
- REV-0027 (archive) certified-properties + F-1/F-2/F-3 → the REV-0041 checklist (map §6). The A-1
  launch/bind certified property is `work/review/REV-0027/result.md:46 @ archive`.
- Plan verdicts: `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §5 runtime-config + §6 step 5.

## Operator resume disposition — 2026-07-23

The operator's QA re-verification request directly authorized the following tightening decisions.
The referenced `work/queue/SIGNAL-R5a-NEEDS-INPUT-DISPOSITION.md` is absent from both the confirmed
`4bb1bfb` base and fetched `origin/codex/signal-r5a-foundation`; this recorded operator instruction
is therefore the disposition authority used for this completion pass.

- **Part B — exact credential strings:** `operator_api_key` and every producer-key-map key/value
  must be exact built-in `str` values. Directly injected subclasses are rejected.
- **D1 — launcher harness:** child processes inherit a sanitized parent environment, remove all
  scoped Signal/Broker/Alpaca and named runtime variables, then apply only the staged overrides.
  `_run` is bounded by a timeout. Launcher assertions and scenarios are unchanged apart from
  Ruff-only layout.
- **D2 — test construction authority:** the flag-on helper requires the exact explicit in-process
  test authority. Zero-argument Uvicorn factory and bare-load selection both raise; every legitimate
  caller supplies the authority.
- **D3 — baseline and ratchet:** Ruff formats/checks only R5a-owned Python files. The ten inherited
  formatter findings are grandfathered without edits, following ADR-007's baseline-and-ratchet
  precedent. A separate, not-yet-numbered formatter-cleanup WO remains follow-up work. The R2
  oracle runs unchanged through CI's pytest module invocation.

The reviewed implementation is frozen at `d78e54fda6a780546cd6892078b209f9ae33438f`.

## Required behavior

- [x] **GATE** (fable_gate): restate goal/scope/done-when/blast-radius before building.
- [x] **Red-first:** pull the R5a test slices from staging; re-baseline the config test's `tls_proxy`
      → `tailnet_serve` (D-R5a-3) and paste the diff + rationale; paste the RED collection.
- [x] **`app/config.py`:** all signal fields (`signal_seat_enabled`, `signal_transport_policy`,
      `operator_api_key` (`repr=False`), `signal_producer_keys` (`repr=False`),
      `signal_invalid_budget_per_epoch`, `signal_server_max_ttl_seconds`) + env parsing +
      `validate_signal_seat_settings` + the operator/producer overlap helper. Turn
      `test_signal_seat_config.py` green.
- [x] **Launcher trio** `app/server.py` (programmatic uvicorn, bind re-validated + `SystemExit(2)`),
      `app/launch_guard.py` (leaf: `validate_transport_bind` + code-owned capability), `app/__main__.py`
      (`python -m app`). Turn `test_signal_seat_launcher.py` green (incl. the subprocess bind proofs).
- [x] **`app/facade/signal_rails.py`** Protocol seam (`RailsDecision`, `is_conforming_rails`).
- [x] **`app/main.py::create_app` skeleton:** new signature + the three construction guards + the
      conditional module-level `app`. Turn `test_signal_seat_launch_guard.py` green. Keep the
      flag-OFF path byte-equivalent to today.
- [x] **`tests/signal_seat_helpers.py`** (construction seam) + the `test_import_boundaries.py`
      `_SANCTIONED_*` hunk (same change as the launcher) + the README correction.
- [x] **Bootstrap non-regression:** verify `harness/bootstrap.py` runs flag-off and its smoke gate
      still passes (paste evidence).
- [x] **Stage `work/review/REV-0041/request.md`** for the Claude seat (REV-0027 checklist,
      archive-ref-renumbered; the never-reviewed items: the master `create_app` REWRITE, the
      transport re-baseline, the D-2a flag-off intermediate state).

## Allowed paths

```yaml
allowed_paths:
  - app/config.py
  - app/server.py                 # new
  - app/launch_guard.py           # new (leaf)
  - app/__main__.py               # new
  - app/facade/signal_rails.py    # new (Protocol seam)
  - app/main.py                   # create_app skeleton ONLY (construction guards + conditional app); R5b extends
  - README.md                     # launch correction only
  - tests/test_signal_seat_config.py        # from staging; tls_proxy→tailnet_serve re-baseline authorized
  - tests/test_signal_seat_launcher.py      # from staging
  - tests/test_signal_seat_launch_guard.py  # from staging
  - tests/signal_seat_helpers.py            # from staging
  - tests/test_import_boundaries.py         # the _SANCTIONED_* hunk ONLY
  - work/active/**                # WO activation + SIGNAL-R5a-STATE.md
  - work/review/REV-0041/         # request.md staging
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/api/**                    # routes_signals, deps, schemas — R5b
  - app/facade/signals.py         # the signal facade (not the rails seam) — R5b
  - app/main.py (middleware/mount)# the operator-enforcement middleware, docs-disable, router mount — R5b (same file, later region)
  - cockpit/**                    # R5b
  - .importlinter                 # routes_signals contract-5 line — R5b
  - app/store/**  app/models.py  app/events/**   # R4, done
  - docs/adr/**   docs/spec/**    # accepted text — consumed, not edited
  - work/ledger.jsonl             # NO close-out line in-session (ends at REVIEW)
  # the R5b-owned test files (routes/facade_reads/malformed_matrix/cockpit_header/totality/phase6 hunk)
```

## Acceptance criteria

- [x] `test_signal_seat_config.py`, `test_signal_seat_launcher.py`, `test_signal_seat_launch_guard.py`
      green (the launcher subprocess proofs included); the config re-baseline diff pasted.
- [x] `test_import_boundaries.py` green with the hunk (no unsanctioned-reacher failure).
- [x] Flag-OFF path byte-equivalent to today; `harness/bootstrap.py` smoke gate green (pasted).
- [x] Operator-dispositioned full gate battery green: `ruff check .`, Ruff format check on the
      eleven R5a-owned Python paths, `mypy app/`, `lint-imports`, the raw R5a/import corpus,
      `python -m pytest -q tests/r2_conformance_oracle.py`,
      `pytest -q tests/test_wo0113_repair_scaling.py`, and `python harness/bootstrap.py`.
      The additional full `pytest -q` non-regression also reached 100% with exit 0.
- [x] `status: REVIEW`, WO in `work/active/`, REV-0041 staged, branch pushed, nothing merged, no
      ledger line. Fable record + this WO's war-game record (M1–M4) present.

## Stop conditions

- Any conflict between the staged tests, accepted ADR/spec, and master on the transport/bind/auth
  surface beyond the D-R5a-3 re-baseline → STOP, record the decision gap (CLAUDE.md conflict rule).
- Green would require an R5b file (routes/deps/middleware/cockpit/`.importlinter`) → STOP; that is
  the boundary, not scope to absorb.
- The bind guard cannot be made construction-time (only request-time achievable) → STOP; a
  reachable-503 is a safety regression, not an acceptable fallback (threat model T-16).
- Never weaken a staged test (the D-R5a-3 re-baseline is the one authorized staged-test edit).

## Completion disposition (post-review)

Expected at close-out: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]` (signal-seat PKL R5a changelog). Close-out
after REV-0041 ACCEPT/ACCEPT-WITH-CHANGES ships status flip + disposition + ledger + file move in one
commit.

## War-game record (.ai-os/core/18)

Scope: **FULL** (human-gated auth/launcher surface + mints a stateful capability). Grounding map +
M1 (above) + M2 + M3 complete. **M4a prospective-hindsight** — six failure narratives; four resolved
`TRACED` (bare-uvicorn-serves, reachable-503, capability-leak, tailnet-non-loopback — all anchored +
subprocess-pinned), two surfaced real findings (transport re-baseline D-R5a-3; the construction-vs-
request boundary).

**M4b refutation (fresh-context agent, 2026-07-22) — COMPLETE.** 10 of 11 D-R5a claims HOLD against
code; **0 safety invariants refuted** — the construction-time bind boundary, the construction-vs-
request split, the rails-seam/R6 decoupling (the launcher's `_load_production_rails` import is
function-local + caught, raising exactly the Runtimeable the positive-control test expects), and the
`.importlinter`-untouched / hunk-only import handling all survived adversarial attack. It caught
**three tracing defects (all bookkeeping, no design change), now fixed in this WO:**
1. **Class-1 (my own miscited anchor):** M3 cited `harness/bootstrap.py:40` as a "bare-uvicorn probe"
   — FALSE; that line is a Windows py-version probe. Real coupling = `pytest --collect-only`
   (`bootstrap.py:117`) imports `app.main` flag-off. Corrected in M3 + D-R5a-11.
2. **Class-2 (unenumerated consumer):** `cockpit/app.py:941` is a third `uvicorn app.main:app`
   doc-string, missing from the inventory. Added (R5b fixes it with cockpit).
3. **Build hazard:** the archive `main.py:57,60-66` R5b module-level imports + middleware must be
   explicitly EXCLUDED from the R5a skeleton (verbatim port → ImportError). Written into D-R5a-4.
All three corrections applied; no M4b finding remains un-resolved. **The R5a decision block is now
ratifiable** per `.ai-os/core/18` (every M4a cause + M4b finding resolves to a `TRACED` fix).
