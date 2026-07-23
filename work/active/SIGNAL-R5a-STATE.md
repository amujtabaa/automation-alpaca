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
| config | PENDING | — | RED corpus not imported yet |
| launcher trio | PENDING | — | Includes sanctioned import-boundary hunk |
| signal_rails seam | PENDING | — | Seam only; provider remains R6 |
| create_app skeleton | PENDING | — | R5b imports and middleware forbidden |
| helper + import-hunk | PENDING | — | Test helper plus `_SANCTIONED_*` only |
| README | PENDING | — | UNDEFINED-not-None correction only |
| green evidence | PENDING | — | Bootstrap plus full gate battery |
| REV-0041 staging | PENDING | — | Claude-seat request; no result/disposition |

## Evidence log

- VERIFIED — 2026-07-23 preflight: clean tree; `83a740b` is an ancestor of `origin/master`;
  feature branch created from `origin/master`; WO exists; ADR-009 Accepted 2026-07-21; staged and
  archive refs readable; `work/review/REV-0041/` free.
- UNVERIFIED — implementation and all acceptance gates pending.
