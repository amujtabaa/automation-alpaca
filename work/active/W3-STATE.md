# W3 state — updated 2026-07-12 (remediation wave complete), tip = origin/feat/execution-envelope
approved-agreement: W3 kickoff prompt + Ameen 2026-07-12 blanket approval: "You may proceed for anything that isn't waiting on SOL" (covers WO-0024 amended, 0025, 0026, 0027, 0028 + prep artifacts).
completed:
  - "WO-0021: be79dda (merge f092ca7), VERIFIED (tests-only charter), RESULT_SUMMARY_KEPT,
     non-gated; chaos & property catalog (regime tapes, interleaving chaos, hypothesis
     properties, dual-store parity). TWO real findings pinned as xfail(strict=True):
     FINDING-W3-staged-order-outlives-preemption (P1, ADR-010 §4 violation, both stores;
     fix drafted as WO-0024, human-gated, awaiting approval) and
     FINDING-W3-lase-pullback-structural-hold (P2, mechanism gap, W4/SOL bake-off axis).
     fable-done in work/completed/keep/WO-0021-*/"
  - "WO-0020: (committed on integration branch — branch hygiene slip, noted), VERIFIED,
     RESULT_SUMMARY_KEPT, non-gated; monitoring tick drive (_run_envelopes, tape buffers,
     fill bridge record-first), facade list/approve/cancel, API routes (approve request model
     IS ExecutionEnvelope ⇒ 422 on missing dispositions), cockpit Envelope Monitor screen.
     fable-done in work/completed/keep/WO-0020-*/"
  - "WO-0019: (merge before be79dda), VERIFIED, RESULT_SUMMARY_KEPT, T3 approved in-chat
     (\"proceed on anything that doesn't rest on SOL work\"); engine seam: store-atomic
     stage_envelope_action claim (write-time validate_action, D-3 mutation-checked) + venue
     leg in reconciliation.execute_envelope_action; redrive_staged_envelope_action;
     quarantine + budget single-spend across crash-restart. fable-done in
     work/completed/keep/WO-0019-*/"
  - "WO-0019a: 124426d (merge 278aabd), VERIFIED, RESULT_SUMMARY_KEPT, T3a approved in-chat;
     BrokerAdapter.replace_order on ABC + alpaca (real SDK name pinned)/mock/sim (chaos);
     ADR-002 taxonomy + deterministic client_order_id duplicate-recovery. Unblocks WO-0019.
     fable-done in work/completed/keep/WO-0019a-*/"
  - "WO-0017: bce10f0 (merge ce40f90), VERIFIED, RESULT_SUMMARY_KEPT, T2 approved in-chat;
     approval surface (ENG-001 shape, zero-artifact HALTED block mutation-checked) + kill-freeze
     + flatten preemption (deferral leaves live exit's envelope); INV-080/081; facade/route
     wiring deferred to WO-0020 (visible deviation, no consumer yet). fable-done in
     work/completed/keep/WO-0017-*/"
  - "WO-0016: 5ca48f2 (merge f0f75cb), VERIFIED, RESULT_SUMMARY_KEPT+ADR_CREATED, T1 approved;
     ADR-010 §3+§6 amendments recorded. fable-done in work/completed/keep/WO-0016-*/"
  - "WO-0018: def2501 (merge 7eaa262), VERIFIED, RESULT_SUMMARY_KEPT, non-gated; regime-adaptive
     spec per FINAL planning drop (d0b1728); divergences amended into the WO (missing LASE docs;
     .importlinter vs pyproject). fable-done in work/completed/keep/WO-0018-*/"
in-flight: NOTHING — remediation wave complete. WO-0028, WO-0024(amended), WO-0026,
  WO-0025, WO-0027 all VERIFIED, merged, pushed. ALL TEN finding pins GREEN
  (tests/test_rev0023_phase_a_pins.py: 32 passed / 0 xfailed; WO-0021 flatten pin flipped;
  only remaining xfail in the whole suite is the LASE structural-hold P2 — SOL/W4 territory).
  Remediation summary: reduce-only hard rail at write time + redrive (INV-084); redrive full
  re-validation + staleness ceiling + preemption sweeps flatten AND kill (INV-081 amended);
  working-order predicate unified live-derived (ADR-010 §5 amended, decide() signature frozen
  intact); inferred-fill record-first bridge (ADR-010 §6 amended); supersession
  refuses-while-live/sweeps-staged/conserves (ADR-010 §3 amended, INV-077 amended); memory
  _atomic envelope snapshot; or-True tautology dead, 14/14 + 9 more mutation-checks killed.
awaiting:
  - REV-0023 PHASE A2 (internal adversarial review of the ASSEMBLED delta f092ca7..HEAD,
    26-agent ultracode workflow) DONE — DREW BLOOD. 10 CONFIRMED findings survive the green gate
    (packet: work/review/REV-0023/phase-a2.md). Headline: **1 P0 (completeness-0)** — the
    single-ACTIVE mandate is scoped per sell_intent_id, NOT per symbol, and close_session orphans
    an ACTIVE envelope by EXPIRing its (session-stamped, APPROVED-not-ORDERED) backing intent →
    two ACTIVE envelopes for one symbol/position across a session boundary. Reproduced + PINNED
    strict-xfail on BOTH stores (tests/test_rev0023_phase_a2_pins.py). REACHABILITY (implementer-
    verified): store-contract-level violation; NOT an active oversell in today's wiring (the
    automatic intent creators dispatch ORDERED legacy orders, never expired at close; create_sell_intent
    does not auto-stamp session_id) — becomes live when the envelope-native exit flow is wired.
    MUST-FIX before T5 merge relies on the single-mandate guarantee. + 5 P1s (concurrency-0 fabricated
    overfill audit event; spec-0 INV-085 terminal-state overclaim [decision gap]; spec-1 redrive
    refusal not durably evented; parity-0 redrive drops now=now → wall clock; mutation-0 WO-0025
    wiring has no killing test) + 3 P2s + 1 P3. Human-gated: P0 fix, concurrency-0/spec-1 (event-log),
    spec-0 (ADR/INV text). Non-gated (may pin+fix under a WO): parity-0, mutation-0, completeness-1,
    parity-1, interface-lift-0. Nine non-P0 pins queued for the remediation WO (not yet written —
    several are gated/decision-gaps and must not be pinned directionally).
    INDEPENDENT REVIEW (REV-0023 Phase-A2, Codex) — INGESTED + DISPOSITIONED. Verdict
    **ACCEPT-WITH-CHANGES, Findings: None** (work/review/REV-0023/result.md — Codex authored it on
    the wo-0001 branch by mix-up; Ameen pushed it; ingested here verbatim onto this lineage). The two
    required changes are SATISFIED (deferred completeness-1/interface-lift-0 in WO-0033 + pure-math-0
    planning-seat per Ameen; human-approval trail = Ameen "Go ahead" for WO-0032/0034), recorded in
    work/review/REV-0023/disposition.md. The reviewer's "could not verify" (full gate + first-principles)
    is covered by the author's full green gate + the 26-agent internal Phase-A2 pass. GATE CLEARED for
    the human-gated surfaces WO-0032 (order-intent) + WO-0034 (event-log truth).
    REMEDIATION WOs DRAFTED (await human approval; nothing implemented):
      - WO-0032 (P0 single-mandate-per-symbol) — DONE (Ameen "go ahead", direction 2a). Per-symbol
        single-ACTIVE guard in BOTH stores (predicate + explicit check + partial unique index moved
        to ON(symbol) WHERE status='active', DROP-then-CREATE for re-init). INV-087 registered. P0
        pin FLIPPED GREEN; tests/test_wo0032_per_symbol_mandate.py (4×2). Breaker-check full suite
        exit 0. Independent-review gate STILL OPEN (human-gated surface — queue REV before a milestone
        relies on it).
      - WO-0033 (non-gated batch) — DONE 3/5 (Ameen "your call"): parity-0 (redrive now=now,
        H11), parity-1 (sqlite validate-before-session-ensure, H10), mutation-0 (WO-0025 union
        coverage test, mutant-killed) all delivered dual-store, gate green, pushed e2ead56.
        DEFERRED w/ rationale: completeness-1 (correct guard but 13 test-site churn + no live
        trigger; await Codex severity) and interface-lift-0 (P3 facade -> Any convention).
      - WO-0034 (event-log fidelity) — DONE (Ameen "go ahead"; spec-0 decision 3a). concurrency-0:
        append_fill gains optional prior_position; the fill bridge passes the pre-fill position so a
        clean exit no longer fabricates fill_overfill_quarantined (mutation-checked; real overfill
        still quarantines). spec-1: redrive refusal now writes a durable envelope_redrive_refused
        event (rail+detail). spec-0: INV-085 narrowed to ACTIVE/FROZEN (terminal late-fill recorded,
        not breached). tests/test_wo0034_eventlog_fidelity.py (4×2). Independent-review gate STILL
        OPEN (event-log-truth surface). pure-math-0 (magnitude band) remains a PLANNING-SEAT decision.
  - T4: human runs Codex Phase B (work/review/W3-codex-review-prompt.md, pin f092ca7 — the pin
    PREDATES the remediation; reconciliation scaffold pre-filled at
    work/review/REV-0023/phase-b-reconciliation.md, incl. the recommendation to hand Codex a
    second short prompt for the f092ca7..tip remediation diff, which also satisfies the
    independent-review requirement for the gated-surface WOs).
  - WO-0029A DONE (both ADR amendments ACCEPTED + implemented: FROZEN→BREACHED INV-085;
    stale-vs-defect split, INV-082 re-amended). WO-0029 B/C remain with the planning seat.
  - SOL-0001: Sol FINISHED (4 files in its sandbox: sol_policy.py, test_sol_policy.py,
    sol_conformance_plugin.py, MANIFEST.md) but NOT YET PUSHED to any branch of this repo —
    Ameen to commit/push (suggested: branch collab/sol-0001 or onto feat/execution-envelope).
    ULTRACODE crosswise-review workflow AUTHORED (work/collab/SOL-0001/ultracode-crosswise.workflow.js — Ameen invoked ultracode for SOL work) + intake protocol at work/collab/SOL-0001/INTAKE-CHECKLIST.md
    (incl. the drift table: Sol's baseline predates the WO-0024..0027 contract-relevant
    changes). Collab-lane codification PREPARED at work/collab/PROPOSAL-cross-model-lane.md
    (yes/no gate).
  - WO-0031 DONE (Sol's two P0s vs the incumbent closed: lifetime-monotone stop INV-086,
    whole-tape screening; probe reported + upsize per adjudication; tranche latch fixed).
  - WO-0030 DONE (interface lift): the full envelope API is on the StateStore ABC + facade
    Protocols; EnvelopeTransitionError relocated to base.py (compat re-export from core.py);
    the four structural Protocols (_EnvelopeStore/_EnvelopeSeamStore/_EnvelopeStoreOps/
    _EnvelopeFacadeOps) and every envelope-seam cast deleted. Deliberate-drift PROVEN:
    dropping OR mistyping a store envelope method now breaks `mypy app/` (was invisible
    behind cast(Any, ...) before). Interface-only, no behavior change; gate green
    (ruff/format, mypy 64, imports 6-0, pytest exit 0). ONE test touched — a naming-heuristic
    guard (test_interface_has_no_fill_mutators) that enumerates "fill"-substring methods;
    record_envelope_fill is now visible on the ABC and added to its expected set with
    rationale (NOT a fills-table mutator; the real forbidden-mutator + sqlite-source guards
    unchanged). Committed 8fa9331 on claude/new-session-gu0z6y. NO remaining approved
    implementation item.
  - T5 EXECUTED (2026-07-15, Ameen directive "Complete the T5 merge"): ADR-010 flipped to
    **Accepted** (independent-review requirement satisfied by the REV-0023 packet — Codex
    ACCEPT-WITH-CHANGES, Findings None, dispositioned RESOLVED); this branch merged into
    feat/execution-envelope and pushed. The THREE deferred Phase-A2 items COMPLETED same day
    (Ameen directive): completeness-1 (price REQUIRED end-to-end + D-019 value guard, INV-089),
    pure-math-0 (MAX_STEP_DEVIATION=0.25 step-deviation band + latest-print fail-quiet, INV-088,
    calibration reviewable), interface-lift-0 (facade envelope returns concretely typed;
    drift-proof kills at deps.py DI seam). All pinned + mutation-checked.
toolchain-incidents (must-read before any destructive git op; never pruned):
  - WO-0017 + WO-0028 (RECURRED 11 WOs apart): reflexive `git checkout <file>` wipes
    UNCOMMITTED WO work. Commit or stash BEFORE any mutation run; restore only committed code.
  - WO-0029A: a mutation-check "0 failures" from a nested-shell `-k` selector was a NO-OP
    selection, not a survivor/kill — verify selectors collected >0 tests (or use explicit test
    ids) before trusting any mutation result.
  - WO-0031: a pin can be VACUOUSLY green — the first SOLF3 pin priced its tape below the
    envelope floor so both arms returned BreachSignal and compared equal regardless of the
    mechanism. Always check the assertion can DISTINGUISH the mechanism (run the discovery
    mutation before trusting a new pin).
  - WO-0030: a background-task "completed (exit code 0)" notification reports the OUTER
    pipeline's exit, not pytest's — a `pytest ... | tail` pipe masks pytest's real code.
    pytest here was RED (one failure) while the wrapper said exit 0. Capture the inner code
    explicitly (`echo EXIT=${PIPESTATUS[0]}`) and read the FAILED/summary line, never trust
    the wrapper's exit for a piped test run. RECURRED (T5 batch, same session, by the same
    author who recorded it): `pytest | tail -2; echo $?` printed EXIT=0 over a REAL failure.
    Structural fix adopted: redirect pytest to a file (`pytest > out 2>&1; echo $?`) so $?
    IS pytest's code — no pipe, nothing to remember.
  - T5 batch (pure-math-0): a NEW safety rail suppressed an OLD one — the deviation band's
    fail-quiet on a suspect LATEST print swallowed the floor-breach path for a genuine -31%
    crash gap (test_gap_below_floor_is_a_breach_signal_never_a_submit went RED). Caught by
    the existing WO-0021 pin, fixed by explicit precedence (floor rail outranks band below
    the floor; pinned in test_puremath0_deviation_band.py). LESSON: any new fail-quiet/
    fail-closed mechanism must state its ORDER against every existing hard rail it can
    shadow, and the full suite must run BEFORE claiming the mechanism done.
anchor-divergences:
  - W3-README branch naming `feat/execution-envelope/wo-00XX` impossible in git (ref namespace);
    using `feat/execution-envelope-wo-00XX`.
  - WO-0020 committed directly on integration branch (hygiene slip, not rewritten).
  - WO-0018: LASE design docs 00/01/02/05 never present in this environment (amended into WO).
  - WO-0018: import contracts live in .importlinter, not pyproject.toml (amended into WO).
  - Planning drop (final) ADR-010 copy predates the ratified WO-0016 amendments — in-repo amended
    ADR kept authoritative (drop NOT copied over it), noted in d0b1728's message.
deferred log (out-of-scope observations):
  - [RESOLVED by WO-0030] interface-lift: the envelope API is now on app/store/base.py's
    StateStore ABC + facade Protocols; the four structural-Protocol workarounds and every
    envelope-seam cast are deleted; EnvelopeTransitionError relocated to base.py.
  - intent→ORDERED linkage decision (planning seat): envelope fills currently don't advance
    SellIntent lifecycle status.
  - synthetic-fill envelope bridge (reconciliation synthetic fills bypass record_envelope_fill).
  - structural-hold mechanism (FINDING P2) — W4/SOL bake-off axis, not a W3 fix.
  - models.py trail_distance_min/max docstrings say "trail distance"; WO-0018(final) defines them
    as ATR MULTIPLES — one-line docstring cleanup for a later WO (models.py forbidden in 0018).
  - compute_working_stop is O(n²) in bars (per-prefix indicator recompute) — fine at tick scale,
    revisit in W4 harness.
  - Container toolchain: /root/.local/bin shims shadowed pinned tools; removed + installed via
    constraints.txt. Fresh containers must redo. Python 3.11 here (authoritative env is 3.12).
  - pytest final summary line suppressed in this container; exit code + [100%] used as evidence.
open decisions:
  - T4 Codex run timing (human executes; scaffold ready).
  - WO-0029 ADR text amendments — yes/no on prepared proposal texts (human gate).
  - intent→ORDERED linkage (planning seat, W4 — decided-deferred in WO-0024 close-out).
  - record_envelope_fill price=None poisons position projection — make price required
    (planning seat; surfaced by WO-0026).

## W3 sequencing status
0016 ✅ → 0018 ✅ → 0017 ✅ → 0019a ✅ → 0019 ✅ → 0020 ✅ → 0021 ✅ → 0022 Phase A ✅ →
REMEDIATION ✅ (0028 → 0024 → 0026 → 0025 → 0027; all pins green) → 0031 ✅ → 0030 ✅ →
**Phase B Codex (T4, human)** → WO-0029 re-cut (planning seat) → T5 ADR-010 Accepted + merge
(human only).

## Branch note (this session)
WO-0030 was developed on `claude/new-session-gu0z6y` (branched from the feat/execution-envelope
tip 209709f, per the session's designated-branch instruction), tip commit 8fa9331. The W3
integration branch feat/execution-envelope is unchanged; a human merge decides how 0030 lands
relative to it (interface-only, no behavior change — trivially mergeable).

## Gate/toolchain reference (this container)
ruff 0.15.20 · mypy 2.2.0 · pytest 9.1.1 · import-linter 2.13 — all == constraints.txt.
Gate: `ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`
(mypy invoked as `mypy app/` per CI; bare `mypy` has no default target in this repo).
Contracts now 6 (sellside-is-a-pure-policy added in WO-0018).
