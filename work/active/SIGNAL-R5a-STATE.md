# Signal Seat R5a — authoritative implementation state

[FABLE • FULL • verification: DIRECT • task: WO-0137 Signal Seat R5a composition-root foundation]

```yaml
fable_gate:
  goal: "Build the construction-time composition-root foundation that refuses to construct or serve the Signal Seat under an absent or invalid launch/config/rails boundary."
  assumptions:
    - "The operator-pasted M1 decision block below is ratified and authoritative."
    - "ADR-009 is Accepted as of 2026-07-21."
    - "The feature flag remains OFF until the joint D-2a milestone."
    - "The staged R5a corpus is the acceptance contract except for the one authorized tls_proxy to tailnet_serve re-baseline."
  approach: "Activate the WO, import the staged tests red-first, implement config then launcher then rails seam then create_app guards in slices, run the full fresh gate battery, and stage REV-0041."
  out_of_scope:
    - "R5b request-time auth, routes, middleware, docs-disable, cockpit, facade/signals, and .importlinter."
    - "R6 rails provider and R7 conversion."
    - "Schema or migration changes."
    - "Ledger close-out, merge, or PR."
  done_when:
    - "All three staged R5a test files and the import-boundary test are green."
    - "Flag-off bootstrap behavior and the complete WO gate battery are freshly green."
    - "WO-0137 is REVIEW in work/active and REV-0041/request.md is staged."
    - "The scoped feature branch is pushed without merging master or opening a PR."
  blast_radius: "Signal Settings/env parsing; backend-owned launcher and capability; rails Protocol seam; create_app construction guards and module export; test-only helper/import allowlist; one README launch correction; WO/review artifacts."
```

## Authoritative M1 decision block

The block below is copied verbatim from the operator kickoff and is authoritative over the
repository work-order copy.

## Decision block (M1 war-game ledger; pre-checked = ratified on paste; edit to override)

Every line was traced against code in the war-game and survived M4b refutation. Anchors are in
WO-0137.

- [x] **D-R5a-1 Branch & corpus.** `codex/signal-r5a-foundation` from master; pull the R5a test
      slices from `origin/codex/signal-tests-staging`: `test_signal_seat_config.py`,
      `test_signal_seat_launcher.py`, `test_signal_seat_launch_guard.py`, `signal_seat_helpers.py`,
      and the `test_import_boundaries.py` `_SANCTIONED_*` hunk.
- [x] **D-R5a-2 Scope = construction-time foundation** (the boundary above).
- [x] **D-R5a-3 Transport = `loopback` | `tailnet_serve`, Funnel/public forbidden.**
      `SIGNAL_TRANSPORT_POLICIES = {"loopback","tailnet_serve"}`. **The ONE authorized staged-test
      edit:** re-baseline `test_signal_seat_config.py`'s `tls_proxy` literal → `tailnet_serve`
      (authorized reconciliation to the accepted ADR — master already says `tailnet_serve`,
      `git grep tls_proxy master` is zero code hits — NOT test-weakening). Paste the one-line diff.
- [x] **D-R5a-4 Three construction guards.** Under the flag, `create_app` raises `RuntimeError` on
      (1) missing/forged capability, (2) invalid config (`validate_signal_seat_settings`:
      blank/absent operator key, empty/invalid producer map, operator≡producer collision, transport
      ∉ set, budget ∉ [1,1000], TTL > 86400), (3) non-conforming rails. Error messages MUST carry
      the tokens the staged regexes match — the TTL message must contain **`A-3`** (the lowercase
      field name won't match a bare `TTL`; staged regex `budget|TTL|A-3|A-4`).
- [x] **D-R5a-5 Conditional module-level `app`.** Flag OFF → `app = create_app()` defined (bare
      uvicorn works, beta unchanged). Flag ON → `app` **NEVER assigned** (not even `None`) → bare
      `uvicorn app.main:app` raises `ImportFromStringError` **before any socket binds**. (Pinned by
      the subprocess proof; couples to `uvicorn==0.51.0`'s exact `'Attribute "app" not found'` text.)
- [x] **D-R5a-6 Bind guard = loopback-only, policy-name-agnostic.** `validate_transport_bind`
      returns `None` for loopback host or UDS, else the A-1 failure string; BOTH policies bind
      loopback (`tailnet_serve` = `tailscale serve` in front of a loopback backend, per accepted ADR).
- [x] **D-R5a-7 Capability = code-owned only.** Mint sentinel never leaves `app/launch_guard.py`;
      not env/config/importable; `is_sanctioned(object()/None)` False; mint is bind-bound.
- [x] **D-R5a-8 Rails SEAM only, not the provider.** Land `app/facade/signal_rails.py`
      (`RailsDecision`, `is_conforming_rails`) + the create_app rails guard. The REAL provider is
      **R6 (WO-0104)**; the launcher's `_load_production_rails` import is function-local + caught,
      raising the exact `RuntimeError` the positive-control test expects when R6 is absent.
- [x] **D-R5a-9 REV citations → archive-ref provenance** (`archive REV-00xx @ origin/archive/...`;
      master's REV-0024 is a different packet).
- [x] **D-R5a-10 Import-boundary hunk SAME change** as `server.py`/`__main__.py`. Do NOT touch
      `.importlinter` (the `routes_signals` line is R5b's).
- [x] **D-R5a-11 Flag stays OFF (D-2a).** Never enable the seat; flag-off is byte-equivalent to
      today. Bootstrap non-regression holds via `pytest --collect-only` (`harness/bootstrap.py:117`)
      importing `app.main` flag-off — NOT a bare-uvicorn probe.

**⚠ BUILD HAZARD (M4b — the one that bites a verbatim port):** the archive `app/main.py` imports R5b
symbols at MODULE level — `routes_signals` (`:57 @ archive`) and the `app.api.deps` helpers
(`:60-66 @ archive`) — plus two operator/producer middleware blocks. Those R5b files are ABSENT on
master; a verbatim port `ImportError`s. Your `create_app` skeleton EXCLUDES those imports and the
middleware, constructs flag-on with master's EXISTING routers and NO signal middleware, and passes
`test_signal_seat_launch_guard.py`'s `assert app is not None`.

## Slice scoreboard

| Slice | Status | Commits | Notes |
|---|---|---|---|
| config | GREEN | `6aee970`, `58ceb32`, `a410546` | 20/20 staged config tests pass; injected types and credential-map immutability hardened |
| launcher trio | BLOCKED (raw Windows proof 7/9) | `6aee970`, `3e6e3ed`, `c968d26`, `a410546` | Seven cases pass; two bare-Uvicorn children fail in Windows stdlib before importing repository code |
| signal_rails seam | GREEN | `6aee970`, `b985174` | 3/3 staged conformity-rejection cases pass; provider remains R6 |
| create_app skeleton | GREEN (direct corpus) | `6aee970`, `c968d26`, `a410546` | 14/14 ordered construction-guard cases pass; reload, exact identity, bind replay, and one-shot controls pass |
| helper + import-hunk | BLOCKED (ADR conflict) | `6aee970`, `3e6e3ed` | Import boundary is 6/6 green, but the staged zero-argument helper is selectable by Uvicorn and conflicts with ADR-009 A-1/A-4 |
| README | GREEN | `3dadec4` | Enabled-seat launch callout says name is undefined, never `None` |
| green evidence | BLOCKED | `5d04d6f`, `a410546` | Lint/type/import/bootstrap/scaling green; raw pytest, formatter, and direct R2 command are not green |
| REV-0041 staging | BLOCKED — NOT CREATED | — | Stop conditions reached; staging a review-ready packet or setting REVIEW would misstate the gates |

## Evidence log

- VERIFIED — 2026-07-23 preflight: clean tree; `83a740b` is an ancestor of `origin/master`;
  feature branch created from `origin/master`; WO exists; ADR-009 Accepted 2026-07-21; staged and
  archive refs readable; `work/review/REV-0041/` free.
- VERIFIED (RED) — targeted `pytest --collect-only`: config collected 20 cases; launcher and guard
  collection failed on absent `app.server` and `app.launch_guard`.
- VERIFIED (RED) — `pytest -q tests/test_signal_seat_config.py`: 20 failed; missing signal fields,
  parsing, validation, and overlap guard.
- VERIFIED (GREEN) — after the surgical `app/config.py` implementation,
  `pytest -q tests/test_signal_seat_config.py`: 20 passed.
- VERIFIED (PARTIAL GREEN) — launcher corpus excluding the two bare-Uvicorn cases: 7 passed;
  bind refusal, loopback/UDS acceptance, `SystemExit(2)` subprocess behavior, and the distinct
  downstream missing-R6 rails failure all hold.
- VERIFIED (GREEN) — `pytest -q tests/test_import_boundaries.py`: 6 passed after adding only
  `app.server` and `app.__main__` while preserving the recorder reachers.
- VERIFIED (RED→GREEN) — guard collection first failed on absent `app.facade.signal_rails`; after
  landing the Protocol seam, its three staged nonconforming-provider cases pass.
- VERIFIED (RED→GREEN) — before the `create_app` rewrite, the guard corpus had 9 failures and 5
  passes; after the ordered construction guards and conditional module export, all 14 pass.
- VERIFIED (RED→GREEN, adversarial) — a public-bind capability minted flag-off could be replayed
  into flag-on construction, and an `object.__new__` instance passed the former `isinstance` guard.
  Exact-type/exact-identity issuance plus current-settings bind revalidation now refuse both.
- VERIFIED (RED→GREEN, adversarial) — equality-based issuance tracking was forgeable; exact identity
  in a weak value registry closes that path. A string subtype could disguise a non-loopback value;
  exact built-in `str` checks now refuse it.
- VERIFIED (RED→GREEN, concurrency) — the first one-shot consume was check-then-pop and two threads
  could both succeed. Locked validation/consumption produced exactly 1 success and 15 refusals.
- VERIFIED (RED→GREEN) — OFF→ON `importlib.reload` formerly retained the old module-level `app`;
  the flag-on branch now removes a stale name and the fresh control reports it undefined.
- VERIFIED (RED→GREEN) — malformed injected signal settings formerly raised raw
  `AttributeError`/`TypeError`, and the frozen dataclass retained a mutable credential map. Invalid
  flag/key/map/budget/TTL types now become construction `RuntimeError`; map and capability state are
  immutable.
- VERIFIED — with a normal inherited Windows environment and the flag on, importing `app.main`
  reports `APP_DEFINED=False`; bare Uvicorn exits before bind with exact
  `Attribute "app" not found in module "app.main"`.
- VERIFIED (platform-adapted) — all 9 unchanged staged launcher cases pass when the test child
  inherits the normal Windows environment and then applies the staged signal overrides.
- BLOCKED (raw harness portability, not repository import) — the unchanged staged launcher test's
  replacement `_ENV` contains a Unix-only `PATH` and omits Windows system variables. Raw local
  execution makes Uvicorn fail in stdlib `_overlapped` with WinError 10106 before it can import
  `app.main`; 7/9 pass raw. No staged-test edit was made.
- BLOCKED (accepted-authority conflict) — `uvicorn.Config(
  "tests.signal_seat_helpers:build_flag_on_app", factory=True).load()` constructs the flag-on app
  with permissive rails. The staged zero-argument helper is therefore selectable from a source-tree
  deployment despite ADR-009 A-1 forbidding a zero-argument authorized factory and A-4 requiring a
  fake to be unselectable by production config/environment. Fixing it changes the staged corpus and
  needs operator authority.
- VERIFIED — post-hardening focused corpus: 40/40 config + construction-guard + import-boundary
  cases pass. Post-hardening raw full suite collected 4320 cases and ended with only the two known
  bare-Uvicorn harness failures (4306 passed, 11 skipped, 1 expected failure, 2 failed).
- VERIFIED — `python harness/bootstrap.py`: exit 0; `ruff check .` and `mypy app/` passed; full
  `pytest --collect-only` completed and includes all 43 staged R5a cases.
- VERIFIED — `ruff check .`, `mypy app/` (74 source files), `lint-imports` (6 contracts), and
  `pytest -q tests/test_wo0113_repair_scaling.py` (13/13) pass.
- BLOCKED (formatter contract) — `ruff format --check .` reports 12 files: ten inherited/out of
  scope and the two immutable staged R5a launcher/guard tests. Formatting the staged files is beyond
  the one authorized test edit; formatting the other ten is outside allowed paths.
- BLOCKED (gate invocation) — the stipulated direct `python tests/r2_conformance_oracle.py` exits
  with `ModuleNotFoundError: app`; the same unchanged oracle exits 0 when the repo root is supplied
  on `PYTHONPATH`. No gate substitution was self-authorized.
- VERIFIED — staged corpus content imported without assertion/scenario changes. The single
  authorized transport-vocabulary reconciliation changes all three necessary textual occurrences
  in `test_signal_seat_config.py` (doc, env input, assertion) from `tls_proxy` to
  `tailnet_serve`; changing only one physical occurrence would make the test self-contradictory.
- VERIFIED — three staged files differ from their staging blobs only by normalization of one final
  empty line; the config blob additionally has only the three coherent authorized transport-literal
  replacements. No assertion or scenario changed.
- NEEDS-INPUT — operator disposition is required for the three decision groups in
  `work/active/SIGNAL-R5a-NEEDS-INPUT.md`.
- BLOCKED — WO-0137 remains ACTIVE. REV-0041 is deliberately absent, the ledger is untouched, and
  no REVIEW/completion claim is made.

## FIX records

```yaml
fable_fix:
  symptom: "The loopback launcher subprocess failed with WinError 10106 before reaching the expected missing-R6 rails diagnostic."
  root_cause: "app.server imported Uvicorn under the staged test's minimal replacement environment before running the rails-presence guard, which initialized Windows networking first."
  evidence: "Six non-bare launcher cases passed; test_subprocess_loopback_passes_bind_then_fails_on_rails failed with WinError 10106 and no rails token."
  fix: "Keep bind validation first, then mint and load production rails before importing Uvicorn or app.main."
  regression_test: "tests/test_signal_seat_launcher.py::test_subprocess_loopback_passes_bind_then_fails_on_rails"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "A capability minted for a public bind while flag-off could construct flag-on, and unissued instances passed the construction guard."
  root_cause: "The guard used isinstance only; recorded bind data was never revalidated and issuance identity was not tracked."
  evidence: "Live controls printed RED_PUBLIC_REUSE True ACCEPTED and RED_OBJECT_NEW True ACCEPTED."
  fix: "Track exact issued identity weakly, require exact capability type/marker, revalidate its bind against current settings, and consume it once."
  regression_test: "Adversarial public-replay, unissued-instance, equality-forgery, and sequential one-shot controls plus the staged guard corpus."
  red_green_verified: true
  attempt: 2
```

```yaml
fable_fix:
  symptom: "Equality tricks, string-subtype bind disguise, and concurrent consumers could defeat the first hardening."
  root_cause: "WeakSet membership was equality-based, bind membership accepted str subclasses, and consume was not atomic."
  evidence: "Independent disproof reproduced each path; the 16-worker pre-fix consume admitted more than one caller."
  fix: "Use id-keyed WeakValueDictionary with identity comparison, exact built-in str bind types, and an RLock around issuance validation/consumption."
  regression_test: "Equality-forgery refusal, disguised non-loopback refusal, and 16-worker consume control (1 true, 15 false)."
  red_green_verified: true
  attempt: 3
```

```yaml
fable_fix:
  symptom: "Reload retained a stale app export; malformed injected settings escaped as raw exceptions; the producer credential map was mutable."
  root_cause: "Reload preserves unassigned globals, dataclass type hints do not validate runtime inputs, and frozen dataclasses do not freeze nested dictionaries."
  evidence: "Pre-fix controls reported RED_RELOAD_AFTER True, raw AttributeError/TypeError cases, and RED_MUTABLE_MAP MUTATED."
  fix: "Pop the app name on flag-on reload, explicitly validate runtime types, and defensively copy credentials into MappingProxyType."
  regression_test: "Reload transition, invalid-type matrix, alias/direct map mutation, staged config and construction-guard corpus."
  red_green_verified: true
  attempt: 1
```

## Current terminal state

```yaml
fable_done:
  status: BLOCKED
  reason: "The immutable staged corpus conflicts with the required Windows proof and accepted zero-argument-factory boundary; two full-battery baseline commands also cannot pass within allowed paths."
  review_ready: false
  work_order_status: ACTIVE
  review_packet_created: false
  ledger_touched: false
  merged: false
```

```yaml
fable_fix:
  symptom: "The first bootstrap stopped at mypy with two incompatible object-to-str-or-None bind arguments."
  root_cause: "mint_launch_capability exposed host and uds as arbitrary object even though the shared bind validator and sanctioned server accept only str or None."
  evidence: "mypy app/ reported app/launch_guard.py arg-type errors for host and uds."
  fix: "Narrow capability host/uds and settings annotations to Optional[str] and Settings; remove the suppression."
  regression_test: "mypy app/ plus tests/test_signal_seat_launch_guard.py"
  red_green_verified: true
  attempt: 1
```
