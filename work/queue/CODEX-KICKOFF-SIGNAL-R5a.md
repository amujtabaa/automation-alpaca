# Codex kickoff — Signal Seat R5a: composition-root foundation (LOCAL, strongest model) — rev-3

> Operator launch prompt, drafted by the planning seat 2026-07-22 (rev-2: defensive reframing +
> exact-identity capability design; rev-3 2026-07-23: adopt the defect-class reporting convention —
> *incorrect type acceptance* / *identity-validation defect* / *non-atomic one-use validation* — and
> fold in the attempt-2 string/loopback/atomic hardening the root agent landed). Paste into a FRESH
> **local** Codex session at the repo root, strongest model, full effort.
>
> **Note (2026-07-23):** R5a is already implemented on `codex/signal-r5a-foundation` @ `4bb1bfb`; the
> three gate blockers are dispositioned in `work/queue/SIGNAL-R5a-NEEDS-INPUT-DISPOSITION.md`. This
> kickoff is retained as the rev-3 contract of record / relaunch vehicle — not a fresh launch.

## Authorized defensive scope (read first)

**This is authorized defensive hardening of the operator's OWN paper-trading application, in the
operator's own repository.** The entire task is to make the app's local API **bind to loopback only**
and **require a local operator key** before it will serve — so that a producer process on the same
host cannot reach positions/orders, and the service cannot be started on a public interface by
mistake. There is **no** offensive activity anywhere in scope: no scanning, no external targets, no
intrusion, no credential theft, no evasion of anyone else's controls. Every "guard," "reject," and
"refuse" below protects the operator's own service. When you write tests or reports, describe them as
**fail-closed assertions that our own guard holds** ("the launcher must refuse to open a listener on
a non-loopback bind"; "the recognizer must reject a non-issued object") — NOT as proof-of-concept
narratives for defeating a control. Keep attacker/exploit vocabulary out of your working notes; the
requirements below are all you need.

---

Codex, you are the implementer seat building **WO-0137 — Signal Seat R5a**, the construction-time
composition-root foundation (the launcher half of the rebuilt WO-0102). Read `AGENTS.md`, the
`CLAUDE.md` safety core, then **`work/queue/WO-0137-signal-r5a-composition-root-foundation.md` IN
FULL** — it is your contract (M1 decision block, M2 capability lifecycle, M3 consumer inventory,
allowed/forbidden paths, acceptance, stop conditions). Fable v3: GATE, red-first, fresh pasted
evidence, FIX root cause. This WO was FULL war-gamed (`.ai-os/core/18`) and cleared M4b (10/11 claims
held against code, 0 safety invariants refuted, 3 tracing defects fixed); the decision block below is
that M1 ledger — pasting it unedited RATIFIES it. **No mid-session gate** — it runs straight to REVIEW.

## The boundary you are building to (construction-time vs request-time)

**R5a = everything that makes `create_app` refuse to CONSTRUCT** under a bad/absent config: the full
signal `Settings` + `validate_signal_seat_settings`, the three construction guards (launch-capability
/ credential-presence / rails-presence), the launcher trio, the `facade/signal_rails` Protocol seam,
the conditional module-level `app`. **R5b (future WO-0138) = the request-time auth surface** (operator
-key middleware, routes, cockpit) — NOT built here. You SHARE `app/main.py::create_app` (land the
skeleton; R5b extends it) and `app/config.py` (you own it; R5b consumes the cred fields). Safe in
between: the seat flag stays OFF until the joint D-2a milestone, so your flag-on code is exercised
only by tests.

## Setup — sync first, verify, then work

- **Step 0 (execute yourself):** `git status --short` (clean, else STOP) → `git fetch origin` →
  confirm `git merge-base --is-ancestor 47a0d9f origin/master && echo BASE-OK` (must print BASE-OK) →
  `git checkout -b codex/signal-r5a-foundation origin/master` →
  `git fetch origin codex/signal-tests-staging archive/claude-wo-0001-install-checks-2x5ys8` (pull the
  RED corpus from staging; read the archive launcher design via
  `git show origin/archive/claude-wo-0001-install-checks-2x5ys8:<path>`).
- **Precondition guard (fail closed — else STOP and report):** (1)
  `work/queue/WO-0137-signal-r5a-composition-root-foundation.md` exists on master; (2)
  `docs/adr/ADR-009-signal-seat-boundary.md` shows **Status: Accepted**; (3) staging + archive refs
  reachable (`git show origin/codex/signal-tests-staging:tests/test_signal_seat_launcher.py | head -3`
  returns content); (4) `work/review/REV-0041/` does NOT exist.
- Never push master. No PR unless asked. Paper-only; zero credentials/broker/live. Pytest scratch in
  OS temp. Strongest local model, full effort.

## Decision block (M1 war-game ledger; pre-checked = ratified on paste; edit to override)

- [x] **D-R5a-1 Branch & corpus.** `codex/signal-r5a-foundation` from master; pull the R5a test
      slices from `origin/codex/signal-tests-staging`: `test_signal_seat_config.py`,
      `test_signal_seat_launcher.py`, `test_signal_seat_launch_guard.py`, `signal_seat_helpers.py`,
      the `test_import_boundaries.py` `_SANCTIONED_*` hunk.
- [x] **D-R5a-2 Scope = construction-time foundation** (the boundary above).
- [x] **D-R5a-3 Transport = `loopback` | `tailnet_serve`, public exposure forbidden.**
      `SIGNAL_TRANSPORT_POLICIES = {"loopback","tailnet_serve"}`. **The ONE authorized staged-test
      edit:** re-baseline `test_signal_seat_config.py`'s `tls_proxy` literal → `tailnet_serve`
      (reconciliation to the accepted ADR — master already says `tailnet_serve`, `git grep tls_proxy
      master` is zero code hits — NOT test-weakening). Paste the one-line diff.
- [x] **D-R5a-4 Three construction guards.** Under `signal_seat_enabled`, `create_app` raises
      `RuntimeError` on (1) missing/unrecognized launch capability, (2) invalid config
      (`validate_signal_seat_settings`: blank/absent operator key, empty/invalid producer map,
      operator≡producer collision, transport ∉ set, budget ∉ [1,1000], TTL > 86400), (3)
      non-conforming rails. Error messages carry the tokens the staged regexes match — the
      TTL-out-of-range message must contain **`A-3`** (staged regex `budget|TTL|A-3|A-4`).
- [x] **D-R5a-5 Conditional module-level `app`.** Flag OFF → `app = create_app()` defined (existing
      `uvicorn app.main:app` start works, beta unchanged). Flag ON → `app` is **never assigned** (not
      `None`) so `uvicorn app.main:app` fails to load the app **before opening a listener** (uvicorn's
      `Config.load()` raises `ImportFromStringError` synchronously, pre-bind). This is a defensive
      **fail-to-start**: the app refuses to serve unless launched through the sanctioned entrypoint.
- [x] **D-R5a-6 Bind guard = loopback-only, policy-name-agnostic.** `validate_transport_bind` returns
      `None` for a loopback host or a Unix socket, else the A-1 failure string; BOTH policies keep the
      backend bound to loopback (`tailnet_serve` = `tailscale serve` fronting a loopback backend, per
      the accepted ADR). The launcher **re-validates its own bind and exits non-zero** before serving
      on anything non-loopback — a self-check, not a probe.
- [x] **D-R5a-7 Capability = code-owned, EXACT-IDENTITY, one-shot (forgery-resistant).** The launch
      capability is an unforgeable proof that construction came through the sanctioned launcher. The
      recognizer accepts ONLY the exact issued instance: **exact-type** (`type(cap) is
      _LaunchCapability`, not `isinstance` — reject subclasses) AND **exact-identity issuance
      tracking** (track the specific minted instance by identity, consume it ONE-SHOT). Do **NOT**
      use equality-/hash-/membership-based recognition (e.g. a `WeakSet` `in`-check) — that is
      spoofable by an object with a crafted `__eq__`/`__hash__`, and it is the concrete vector the
      attempt-1 internal-adversarial test found. `is_sanctioned` returns False for `object()`, `None`,
      a subclass instance, an equality-spoofing clone, a copied-private-fields clone, and an
      already-consumed capability. Add fail-closed negative tests asserting **each of those forged
      forms is REJECTED** — write them as rejection assertions ("must be refused"), not as
      step-by-step forgery constructions. The mint re-validates the bind (bind-bound).
- [x] **D-R5a-8 Rails SEAM only, not the provider.** Land `app/facade/signal_rails.py`
      (`RailsDecision`, `is_conforming_rails`) + the create_app rails guard. The REAL provider is
      **R6 (WO-0104)**; the launcher's rails load is function-local + caught, raising the exact
      `RuntimeError` the positive-control test expects when R6 is absent.
- [x] **D-R5a-9 REV citations → archive-ref provenance** (`archive REV-00xx @ origin/archive/...`).
- [x] **D-R5a-10 Import-boundary hunk SAME change** as `server.py`/`__main__.py`. Do NOT touch
      `.importlinter` (the `routes_signals` line is R5b's).
- [x] **D-R5a-11 Flag stays OFF (D-2a).** Never enable the seat; flag-off is byte-equivalent to today.
      Bootstrap non-regression holds via `pytest --collect-only` (`harness/bootstrap.py:117`) importing
      `app.main` flag-off.

**⚠ BUILD HAZARD (M4b):** the archive `app/main.py` imports R5b symbols at MODULE level —
`routes_signals` (`:57 @ archive`) and the `app.api.deps` helpers (`:60-66 @ archive`) — plus two
middleware blocks. Those R5b files are ABSENT on master; a verbatim port `ImportError`s. Your
`create_app` skeleton EXCLUDES those imports and the middleware, constructs flag-on with master's
EXISTING routers and NO signal middleware, and passes `test_signal_seat_launch_guard.py`.

## Adversarial controls: name the defect class, express it as a regression test (the reporting convention)

The capability recognizer and the launcher get **fail-closed negative tests** — normal and required.
The known defect classes on this surface are ALREADY CLOSED by the D-R5a-4/D-R5a-7 design below; the
tests CONFIRM they stay closed. To keep both the implementation and any review report filter-safe,
follow one convention: **name the defect class and express the control as a local regression test —
do not emit reusable bypass recipes or step-by-step exploit payloads** (in code, comments, commit
messages, or the REV-0041 request). Use these terms:

- **"incorrect type acceptance"** — the recognizer/validator accepting a non-exact type (a subclass,
  or a `str` subtype). Control: a regression test asserting the exact-type check rejects it.
- **"identity-validation defect"** — accepting anything other than the exact issued instance.
  Control: a regression test asserting a non-issued/cloned object is rejected.
- **"non-atomic one-use validation"** — a consumption check that isn't atomic. Control: a regression
  test asserting concurrent double-consumption yields exactly one success.

Report any defect (if you find a new one) as **cause · impact · affected local files · resolution ·
pass/fail evidence** — narrowly, as a regression test, not an exploit narrative. **Do NOT spin up an
open-ended "try to break the guard" adversarial-discovery pass on the launch/capability layer** — the
three classes above are pre-closed and the independent **REV-0041 Claude-seat review is the sanctioned
adversarial net for this surface** (it verifies rejection of each class, in the same named terms). This
scope is authorized defensive software assurance of the operator's own local application — no external
target, network probing, credential access, persistence, or offensive objective anywhere.

## Continuity across pauses and compaction

1. **FIRST commit** (with WO activation → ACTIVE, move to `work/active/`): create
   `work/active/SIGNAL-R5a-STATE.md` with (a) this decision block **as pasted** (authoritative) and
   (b) a scoreboard: config / launcher trio / signal_rails seam / create_app skeleton / helper+import
   -hunk / README / green evidence / REV-0041 staging.
2. Update it at every slice boundary; intermediate red is fine, final state green.
3. **After ANY pause/compaction** re-read: this kickoff → `SIGNAL-R5a-STATE.md` → WO-0137. Verify with
   `git log`/`git status`, never memory.

## The work — recommended slice order

1. **Red-first:** pull the R5a test slices from staging; re-baseline the config test (D-R5a-3, paste
   the diff); paste the RED collection.
2. **`app/config.py`** — all signal fields (secrets `repr=False`) + env parsing +
   `validate_signal_seat_settings` + the operator/producer overlap helper. → `test_signal_seat_config.py` green.
3. **Launcher trio** `app/launch_guard.py` (leaf: `validate_transport_bind` + the exact-identity
   code-owned capability, D-R5a-7), `app/server.py` (programmatic uvicorn, self-validates its bind +
   exits non-zero, function-local rails load), `app/__main__.py`. → `test_signal_seat_launcher.py`
   green (the launcher fail-to-start proofs).
4. **`app/facade/signal_rails.py`** Protocol seam.
5. **`app/main.py::create_app` skeleton** — new signature + the three guards + conditional
   module-level `app`; **exclude the archive's R5b module-level imports + middleware (BUILD HAZARD)**;
   keep the flag-OFF path byte-equivalent. → `test_signal_seat_launch_guard.py` green (incl. the
   forgery-rejection negative tests from D-R5a-7).
6. **`tests/signal_seat_helpers.py`** + the `test_import_boundaries.py` `_SANCTIONED_*` hunk (same
   change as the launcher) + the README correction ("app is None" → leave-name-UNDEFINED).
7. **Bootstrap non-regression:** run `python harness/bootstrap.py`; confirm the smoke gate stays green.
   **Full gate battery**, fresh pasted output: `ruff check .`, `ruff format --check .`, `mypy app/`,
   `lint-imports`, `pytest -q` (OS-temp basetemp), `python tests/r2_conformance_oracle.py`,
   `pytest -q tests/test_wo0113_repair_scaling.py`.
8. **Stage `work/review/REV-0041/request.md`** for the Claude seat: scope, commit list, the REV-0027
   certified-properties checklist (archive-ref-renumbered), and the never-reviewed items — the master
   `create_app` REWRITE, the transport re-baseline, the exact-identity capability design (D-R5a-7),
   the D-2a flag-off intermediate state. Flip WO-0137 to `status: REVIEW` (stays in `work/active/`).
   Do NOT close/ledger/merge it.

## Rules

1. **The boundary is hard.** `app/api/**`, `app/facade/signals.py`, the operator-enforcement
   middleware / docs / router-mount regions of `main.py`, `cockpit/**`, `.importlinter`, and the
   R5b-owned test files are FORBIDDEN. If green seems to need them, that's a finding, not scope.
2. **Never weaken a staged test.** The D-R5a-3 config re-baseline is the ONE authorized staged edit.
3. **The bind guard is construction-time (fail-to-start), never request-time.** A service that starts
   and then answers on a non-loopback interface is a defect, not a fallback — if you can only achieve
   a request-time check, STOP and report.
4. Adversarial/negative tests are rejection assertions, not bypass PoCs (see the filter note above).
5. Evidence discipline: VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT, fresh pasted output. Ledger
   untouched. End-of-session: final scoreboard, REV-0041 staged, branch pushed. Nothing merged.

## NOT in this session

- The REV-0041 review itself (Claude seat, after). WO-0137 close-out/merge (post-disposition).
- **R5b (WO-0138)** — the request-time auth/routes/cockpit surface — its own FULL war-game later.
- R6 (rails provider / WO-0104), R7 (conversion). GAP-10 (signal-sell-vs-envelope + multi-exit) is an
  operator decision R7 needs — not now.
- Anything touching `codex/signal-tests-staging` (live corpus; never deleted or merged red).
