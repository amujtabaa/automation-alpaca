# Codex kickoff — Signal Seat R5a: composition-root foundation (LOCAL, strongest model)

> **Reset-cleanup supersession — 2026-08-05.** Historical kickoff only. ADR-022 disables and
> unmounts Signal Seat for reset beta. Do not use this prompt or fetch its retired staging-branch
> dependency; future reactivation requires a new ADR/work order and the durable requirements in
> `docs/spec/signal-seat/07-malformed-quarantine-conformance.md`.

> Operator launch prompt, drafted by the planning seat 2026-07-22. Paste into a FRESH **local**
> Codex session at the repo root. R5a is a human-gated auth/launcher/transport **security boundary**
> → strongest local model, full effort. The decision block below is the **M1 assumption ledger** of
> a FULL `.ai-os/core/18` war-game that cleared M4b (10/11 claims held against code, 0 safety
> invariants refuted, 3 tracing defects fixed) — pasting it unedited RATIFIES it. **No mid-session
> gate** (R5a has no schema/migration; everything is pre-traced) — it runs straight to REVIEW.

---

Codex, you are the implementer seat building **WO-0137 — Signal Seat R5a**, the construction-time
composition-root foundation (the launcher half of the rebuilt WO-0102). Read `AGENTS.md`, the
`CLAUDE.md` safety core, then **`work/queue/WO-0137-signal-r5a-composition-root-foundation.md` IN
FULL** — it is your contract (the M1 decision block, the M2 capability lifecycle, the M3 consumer
inventory, the war-game record, allowed/forbidden paths, acceptance, stop conditions). Fable v3:
GATE, red-first, fresh pasted evidence, FIX root cause. No completion claims without evidence.

## The boundary you are building to (construction-time vs request-time)

**R5a = everything that makes `create_app` refuse to CONSTRUCT** under a bad/absent config: the full
signal `Settings` + `validate_signal_seat_settings`, the three construction guards (launch-capability
/ credential-presence / rails-presence), the launcher trio, the `facade/signal_rails` Protocol seam,
the conditional module-level `app`. **R5b (future WO-0138) = everything that makes a REQUEST fail
auth** (operator-key middleware, routes, cockpit) — you do NOT build it here. You SHARE
`app/main.py::create_app` (land the skeleton; R5b extends it) and `app/config.py` (you own it; R5b
consumes the cred fields). Safe in between: the seat flag stays OFF until the joint D-2a milestone,
so your flag-on code is exercised only by tests.

## Setup — sync first, verify, then work

- **Step 0 (execute yourself):** `git status --short` (clean, else STOP) → `git fetch origin` →
  confirm `git merge-base --is-ancestor 83a740b origin/master && echo BASE-OK` (must print BASE-OK;
  the tip may be newer) → `git checkout -b codex/signal-r5a-foundation origin/master` →
  `git fetch origin archive/claude-wo-0001-install-checks-2x5ys8` (the retained archive launcher
  design is read via
  `git show origin/archive/claude-wo-0001-install-checks-2x5ys8:<path>`).
- **Precondition guard (fail closed — ALL must hold, else STOP and report which failed):**
  1. `work/queue/WO-0137-signal-r5a-composition-root-foundation.md` exists on master. If missing,
     the planning branch (`claude/signal-r4-kickoff-planning-354qc0`) hasn't merged — STOP; operator
     merges it first.
  2. `docs/adr/ADR-009-signal-seat-boundary.md` shows **Status: Accepted** (2026-07-21).
  3. **Historical only:** the former staging ref is retired and must not be queried or recreated.
     The retained archive reference may be read for provenance; any future Signal Seat work must
     use a newly authorized work order and the bounded conformance specification.
  4. `work/review/REV-0041/` does NOT exist (namespace free).
- Never push master. No PR unless asked. Paper-only; zero credentials/broker/live. Pytest scratch in
  OS temp, never repo-root. Strongest local model, full effort — this is the localhost security
  boundary (D-HOST-1).

## Decision block (M1 war-game ledger; pre-checked = ratified on paste; edit to override)

Every line was traced against code in the war-game and survived M4b refutation. Anchors are in
WO-0137.

- [x] **D-R5a-1 Historical branch/corpus note.** `codex/signal-r5a-foundation` formerly used
      staging test slices. The source branch is retired and not a future test source; see the
      bounded conformance specification for the retained requirement.
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

## Continuity across pauses and compaction

1. **FIRST commit** (with WO activation → ACTIVE, move to `work/active/`): create
   `work/active/SIGNAL-R5a-STATE.md` with (a) this decision block **as pasted** (verbatim,
   authoritative over the repo copy) and (b) a scoreboard: slice → status → commits → notes (rows:
   config / launcher trio / signal_rails seam / create_app skeleton / helper+import-hunk / README /
   green evidence / REV-0041 staging).
2. Update it at every slice boundary; intermediate red on the branch is fine, final state green.
3. **After ANY pause/compaction** re-read, in order: this kickoff → `SIGNAL-R5a-STATE.md` → WO-0137.
   Verify with `git log`/`git status`, never memory.

## The work — recommended slice order

1. **Historical only:** this former red-first instruction used a staging test corpus that is now
   retired. Do not execute or recreate it; future work needs fresh authorized tests.
2. **`app/config.py`** — all signal fields (secrets `repr=False`) + env parsing +
   `validate_signal_seat_settings` + the operator/producer overlap helper. → `test_signal_seat_config.py` green.
3. **Launcher trio** `app/launch_guard.py` (leaf: `validate_transport_bind` + code-owned capability),
   `app/server.py` (programmatic uvicorn, bind re-validated + `SystemExit(2)`, function-local rails
   load), `app/__main__.py`. → `test_signal_seat_launcher.py` green (subprocess bind proofs).
4. **`app/facade/signal_rails.py`** Protocol seam.
5. **`app/main.py::create_app` skeleton** — new signature + the three guards + conditional
   module-level `app`; **exclude the archive's R5b module-level imports + middleware (BUILD HAZARD)**;
   keep the flag-OFF path byte-equivalent. → `test_signal_seat_launch_guard.py` green.
6. **`tests/signal_seat_helpers.py`** + the `test_import_boundaries.py` `_SANCTIONED_*` hunk (same
   change as the launcher) + the README correction ("app is None" → leave-name-UNDEFINED).
7. **Bootstrap non-regression:** run `python harness/bootstrap.py`; confirm the smoke gate stays
   green (the flag-off collect path). **Full gate battery**, fresh pasted output: `ruff check .`,
   `ruff format --check .`, `mypy app/`, `lint-imports`, `pytest -q` (OS-temp basetemp),
   `python tests/r2_conformance_oracle.py`, `pytest -q tests/test_wo0113_repair_scaling.py`.
8. **Stage `work/review/REV-0041/request.md`** for the Claude seat (cross-model rule): scope, commit
   list, the REV-0027 certified-properties checklist (archive-ref-renumbered), and the never-reviewed
   items — the master `create_app` REWRITE, the transport re-baseline, the D-2a flag-off intermediate
   state. Flip WO-0137 to `status: REVIEW` (stays in `work/active/`). Do NOT close/ledger/merge it.

## Rules

1. **The boundary is hard.** `app/api/**`, `app/facade/signals.py`, the operator-enforcement
   middleware / docs-disable / router-mount regions of `main.py`, `cockpit/**`, `.importlinter`, and
   the R5b-owned test files are FORBIDDEN. If green seems to need them, that's a finding, not scope.
2. **Never weaken a staged test.** The D-R5a-3 config re-baseline is the ONE authorized staged edit;
   everything else stays as staged.
3. **The bind guard is construction-time, never request-time.** A reachable-503 on a forbidden port
   is a safety regression (threat model T-16), not a fallback — if you can only achieve request-time,
   STOP and report.
4. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT, fresh pasted output.
5. Ledger untouched this session (review-gated WO). End-of-session: final scoreboard, REV-0041
   staged, NEEDS-INPUT batch, branch pushed. Nothing merged.

## NOT in this session

- The REV-0041 review itself (Claude seat, out-of-session, after).
- WO-0137 close-out/merge (post-disposition, planning seat coordinates).
- **R5b (WO-0138)** — the auth/routes/cockpit request-time surface — gets its own FULL war-game
  (folding the threat model's GAP-01/02/05/06) when R5a lands.
- R6 (rails provider / WO-0104), R7 (conversion). GAP-10 (signal-sell-vs-envelope + multi-exit) is
  an operator decision R7 needs — not now.
- The former staging corpus is retired. Do not recreate it; use only a future authorized work
  order and its bounded conformance specification.
