# Signal Seat R5a — planning-seat disposition of the NEEDS-INPUT batch

> Drafted by the planning seat 2026-07-23, resolving the three STOP conditions Codex recorded in
> `work/active/SIGNAL-R5a-NEEDS-INPUT.md` on branch `codex/signal-r5a-foundation` @ `4bb1bfb`.
> Codex did the right thing: all three are genuine gate blockers, the security hardening is complete
> (STATE FIX records confirm exact-type / exact-identity / atomic one-shot / exact built-in `str`
> all landed), and WO-0137 correctly stayed **ACTIVE** rather than falsely claiming REVIEW.
>
> Convention adopted for this whole surface (per the operator relay): **name the defect class,
> express each control as a local regression test; no reusable bypass procedures or exploit
> payloads** — in code, comments, commit messages, or the REV-0041 packet. Defect-class terms:
> *incorrect type acceptance*, *identity-validation defect*, *non-atomic one-use validation*,
> *capability reacquisition via importable factory*. This is authorized defensive software assurance
> of the operator's own local application — no external target, network probing, credential access,
> persistence, or offensive objective anywhere.

Decision-block convention (same as the kickoff): **pre-checked = ratified; edit a line to override.**

---

## Decision 1 — launcher cross-platform harness correction → **AUTHORIZE Option 1 (bounded)**

- [x] **D1-RULING — authorize the staged-test *harness* correction; reject the accept-foreign-OS-evidence path.**

**Why.** The launcher *code* is proven correct: with a normal inherited environment plus the staged
Signal Seat overrides, **all 9 unchanged staged cases pass** and produce the exact
`Attribute "app" not found in module "app.main"` pre-bind failure D-R5a-5 requires — no listener
opens. The two failing raw cases fail in Windows stdlib `_overlapped` (WinError 10106) **before
Uvicorn imports repository code**, because the staged test replaces the *entire* child environment
with a Unix-only minimal set that omits the OS variables Windows networking needs. That is a
test-**harness** portability defect, not a code defect and not a test-weakening.

**Authorized edit (beyond D-R5a-3), tightly bounded — assertions and scenarios UNCHANGED:**
1. Build the child environment from a **sanitized inherited base**: start from the parent
   environment, then **delete every app-relevant key** so hermeticity for the variables that matter
   is preserved — scrub set: `SIGNAL_SEAT_ENABLED`, `SIGNAL_TRANSPORT_POLICY`,
   `SIGNAL_PRODUCER_KEYS`, `OPERATOR_API_KEY`, and any other `SIGNAL_*`, `BROKER_*`, `ALPACA_*`,
   `STATE_STORE`, `MARKET_DATA_FEED`, `ENABLE_TAPE_RECORDER` — **then** apply the explicit staged
   Signal Seat overrides on top. (Inherit OS plumbing; never inherit app posture.)
2. Add the `_run` timeout so a hung child fails fast instead of stalling the gate.
3. **No assertion or scenario changes** — the exact pre-bind `Attribute "app" not found …` assertion
   and every bind/UDS/exit-code check stay byte-for-byte.

**Rejected — Option 2 (accept POSIX evidence for the local Windows gate):** it leaves a permanent
2-red state on the operator's own gate and on any non-inheriting runner. A portable harness serves
**both** the Windows local gate and the POSIX deployment target (the launcher itself builds a POSIX
env), so portability is strictly better than a foreign-OS evidence exception.

**Review hook:** REV-0041 confirms the launcher-test diff is confined to **environment construction +
the `_run` timeout** — zero assertion/scenario drift.

---

## Decision 2 — importable zero-argument factory (ADR-009 A-1/A-4) → **AUTHORIZE Option 1; reject Option 2 for this repo**

- [x] **D2-RULING — confine the flag-on helper behind explicit in-process test authority and add a hostile-import-string rejection proof; do NOT rely on a packaging exclusion.**

**Why.** This is a real safety-surface finding and stopping was correct. The staged
`tests.signal_seat_helpers:build_flag_on_app` is a **zero-argument Uvicorn factory** (`factory=True`)
that re-mints a launch capability and wires permissive rails, so
`uvicorn --factory tests.signal_seat_helpers:build_flag_on_app` constructs a **servable flag-on app**
— the *capability reacquisition via importable factory* defect. That is exactly what ADR-009 A-1
forbids (no zero-argument authorized factory that can reacquire the capability) and what A-4 forbids
(a permissive fake selectable by production config/environment). **Option 2 (packaging exclusion)
does not close the hole in this repo:** deployment *is* the source tree — the operator runs from the
checkout, there is no wheel/artifact boundary — so the test module stays importable in the real
runtime and a "not in the built artifact" proof is vacuous.

**Authorized edit (beyond D-R5a-3), on the launch/capability corpus:**
1. The flag-on helper **requires explicit, in-process-only test authority** (an argument/sentinel
   that env, config, and the Uvicorn CLI cannot supply). The **zero-argument `factory=True` load
   path must raise.**
2. Add a **hostile import-string rejection proof**: loading the helper as
   `uvicorn.Config("tests.signal_seat_helpers:build_flag_on_app", factory=True).load()` — and the
   bare attribute-import form — **must raise**, i.e. the capability is unreacquirable through any
   importable path. Express it as a rejection assertion under the named defect class, not a bypass
   recipe.
3. The in-process callers that legitimately need a flag-on app pass the explicit authority.

This satisfies **both** A-1 (no zero-argument reacquisition) and A-4 (the fake is confined —
unselectable by production config/environment/CLI), converting the staged hole into a proof of the
boundary.

**Review hook (gated surface):** this modifies the launch/capability boundary, so REV-0041 **must**
independently confirm (a) every importable/zero-argument construction path raises and (b) the
explicit-authority path is the only route to a flag-on app — using the named defect-class terms.

---

## Decision 3 — inherited gate-baseline conflicts → **AUTHORIZE Option 1 (bounded); do NOT reformat out-of-scope files in R5a**

- [x] **D3-RULING — grandfather the pre-existing formatter debt and use CI's canonical oracle invocation; R5a does not own repo-wide cleanup.**

**Evidence gathered by the planning seat (2026-07-23, against the pre-R5a baseline):**
- **CI does not gate on `ruff format --check .`.** `.github/workflows/ci.yml` runs `ruff check .`
  (lint), `mypy app/`, `lint-imports`, `python -m pytest -q tests/r2_conformance_oracle.py`, and the
  suite — **never** `ruff format --check`. The `ruff format --check .` in the CLAUDE.md build block
  is a *local* ritual stricter than CI.
- **The 10 formatter files are pre-existing and not R5a's.** `ruff format --check .` on the clean
  pre-R5a branch reports the identical 10: `app/recorder/{__init__,models,store}.py`,
  `harness/bootstrap.py`, four pre-existing `tests/test_*` files, and
  `work/review/AUDIT-0002-priorwork/probe_review_integrity.py`. None are R5a-authored; they were
  tolerated because CI never checked format. (R5a's tree shows 12 = these 10 + the 2 immutable
  staged launcher/guard tests.)
- **The R2 oracle content is fine; only the *documented command* is wrong.** CI's
  `python -m pytest -q tests/r2_conformance_oracle.py` passes; the CLAUDE.md-documented
  `python tests/r2_conformance_oracle.py` fails with `ModuleNotFoundError: app` (repo root not on
  path). The oracle itself is unchanged.

**Disposition:**
- **Formatter:** R5a **must not** reformat the 10 out-of-scope files (scope + diff-pollution) nor the
  immutable staged tests — *except* the launcher/guard tests it now owns via Decisions 1 & 2, which
  it formats as part of those authorized edits. Record the 10 inherited files as a **grandfathered
  formatter baseline** mirroring the ADR-007 mypy baseline-and-ratchet precedent (see
  `work/completed/keep/WO-0012-mypy-grandfather-burndown/`). R5a's own authored files must pass
  `ruff format --check`. A **separate follow-up cleanup WO** burns the 10 down — it is **not** a
  blocker on this foundation milestone.
- **R2 oracle:** the authorized gate invocation for R5a's battery is CI's canonical
  `python -m pytest -q tests/r2_conformance_oracle.py` (the check is unchanged — no oracle-content
  substitution). Correcting the documented command in CLAUDE.md / repo-primer is a **non-gated doc
  touch-up** that may ride in R5a's close-out or a separate doc WO; do **not** self-author an oracle
  content change.

**Rejected — Option 2 (block R5a on separate baseline cleanup + rebase):** it delays a foundation
milestone on janitorial debt CI does not enforce. The grandfather-baseline path is the repo's own
established mechanism for exactly this.

---

## Authorized-edit ledger (the complete allowed set — everything else in the staged corpus stays immutable)

1. **D-R5a-3** — transport literal `tls_proxy → tailnet_serve` in `test_signal_seat_config.py` (3
   coherent occurrences).
2. **D1** — `test_signal_seat_launcher.py` child-environment construction (sanitized-inherited base +
   explicit overrides) + `_run` timeout. No assertion/scenario change.
3. **D2** — `tests/signal_seat_helpers.py` explicit-authority confinement + a hostile-import-string
   rejection proof (helper + its callers + the new negative test).

REV-0041 verifies the staged-corpus diff is confined to exactly these three; any other assertion or
scenario change is a review failure.

## Resume gate (unchanged from NEEDS-INPUT, now unblocked)

With D1/D2/D3 recorded: rerun the exact raw launcher corpus (now portable), complete the gate battery
(format check scoped to R5a's authored files + the grandfathered baseline; oracle via
`python -m pytest -q tests/r2_conformance_oracle.py`), then set WO-0137 → **REVIEW** and stage
`work/review/REV-0041/request.md`. Only then does the review seat pick it up.
