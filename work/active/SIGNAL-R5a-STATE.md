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
| config | GREEN | `6aee970`, `58ceb32` | 20/20 staged config tests pass |
| launcher trio | GREEN (Windows-adapted) | `6aee970`, `3e6e3ed`, `c968d26` | 9/9 unchanged staged cases pass when mandatory Windows child env is preserved |
| signal_rails seam | GREEN | `6aee970`, `b985174` | 3/3 staged conformity-rejection cases pass; provider remains R6 |
| create_app skeleton | GREEN | `6aee970`, `c968d26` | 14/14 ordered construction-guard cases pass |
| helper + import-hunk | GREEN | `6aee970`, `3e6e3ed` | Helper imported; launcher allowlist hunk passes 6/6 boundary tests |
| README | GREEN | README commit (this slice) | Enabled-seat launch callout says name is undefined, never `None` |
| green evidence | PENDING | — | Bootstrap plus full gate battery |
| REV-0041 staging | PENDING | — | Claude-seat request; no result/disposition |

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
- VERIFIED — with a normal inherited Windows environment and the flag on, importing `app.main`
  reports `APP_DEFINED=False`; bare Uvicorn exits before bind with exact
  `Attribute "app" not found in module "app.main"`.
- VERIFIED (platform-adapted) — all 9 unchanged staged launcher cases pass when the test child
  retains mandatory Windows system variables/path in addition to its five explicit signal vars.
- BLOCKED (raw harness portability, not repository import) — the unchanged staged launcher test's
  replacement `_ENV` contains a Unix-only `PATH` and omits Windows system variables. Raw local
  execution makes Uvicorn fail in stdlib `_overlapped` with WinError 10106 before it can import
  `app.main`; 7/9 pass raw. No staged-test edit was made.
- VERIFIED — staged corpus content imported without assertion/scenario changes. The single
  authorized transport-vocabulary reconciliation changes all three necessary textual occurrences
  in `test_signal_seat_config.py` (doc, env input, assertion) from `tls_proxy` to
  `tailnet_serve`; changing only one physical occurrence would make the test self-contradictory.
- UNVERIFIED — implementation and all acceptance gates pending.

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
