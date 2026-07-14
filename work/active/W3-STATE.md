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
  - WO-0030 (interface lift): APPROVED in-chat, next in queue (not started — the last
    approved item; everything else in this list is human/planning-seat/SOL-blocked).
  - T5: ADR-010 Accepted + W3 merge — human only, after Phase B reconciliation. Remaining
    blockers: the two prepared ADR text amendments + Phase B verdict. All P0/P1 code defects
    are remediated and pinned at tip.
toolchain-incidents (must-read before any destructive git op; never pruned):
  - WO-0017 + WO-0028 (RECURRED 11 WOs apart): reflexive `git checkout <file>` wipes
    UNCOMMITTED WO work. Commit or stash BEFORE any mutation run; restore only committed code.
  - WO-0029A: a mutation-check "0 failures" from a nested-shell `-k` selector was a NO-OP
    selection, not a survivor/kill — verify selectors collected >0 tests (or use explicit test
    ids) before trusting any mutation result.
anchor-divergences:
  - W3-README branch naming `feat/execution-envelope/wo-00XX` impossible in git (ref namespace);
    using `feat/execution-envelope-wo-00XX`.
  - WO-0020 committed directly on integration branch (hygiene slip, not rewritten).
  - WO-0018: LASE design docs 00/01/02/05 never present in this environment (amended into WO).
  - WO-0018: import contracts live in .importlinter, not pyproject.toml (amended into WO).
  - Planning drop (final) ADR-010 copy predates the ratified WO-0016 amendments — in-repo amended
    ADR kept authoritative (drop NOT copied over it), noted in d0b1728's message.
deferred log (out-of-scope observations):
  - interface-lift WO needed: app/store/base.py ABC + facade ABCs lack envelope API; FOUR
    structural-Protocol workarounds accumulated (approval/envelope.py, reconciliation.py,
    monitoring.py, routes_trading.py) + EnvelopeTransitionError relocation from store/core.py.
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
  - WO-0030 interface-lift approval.
  - intent→ORDERED linkage (planning seat, W4 — decided-deferred in WO-0024 close-out).
  - record_envelope_fill price=None poisons position projection — make price required
    (planning seat; surfaced by WO-0026).

## W3 sequencing status
0016 ✅ → 0018 ✅ → 0017 ✅ → 0019a ✅ → 0019 ✅ → 0020 ✅ → 0021 ✅ → 0022 Phase A ✅ →
REMEDIATION ✅ (0028 → 0024 → 0026 → 0025 → 0027; all pins green) →
**Phase B Codex (T4, human)** → WO-0029 re-cut (planning seat) → T5 ADR-010 Accepted + merge
(human only).

## Gate/toolchain reference (this container)
ruff 0.15.20 · mypy 2.2.0 · pytest 9.1.1 · import-linter 2.13 — all == constraints.txt.
Gate: `ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`
(mypy invoked as `mypy app/` per CI; bare `mypy` has no default target in this repo).
Contracts now 6 (sellside-is-a-pure-policy added in WO-0018).
