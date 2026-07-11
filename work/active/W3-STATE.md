# W3 state — updated 2026-07-12, tip f092ca7 (feat/execution-envelope)
approved-agreement: W3 kickoff prompt (work/queue/W3-KICKOFF-PROMPT.md, FINAL drop version), pasted 2026-07-11
completed:
  - "WO-0021: be79dda (merge f092ca7), VERIFIED (tests-only charter), RESULT_SUMMARY_KEPT,
     non-gated; chaos & property catalog (regime tapes, interleaving chaos, hypothesis
     properties, dual-store parity). TWO real findings pinned as xfail(strict=True):
     FINDING-W3-staged-order-outlives-preemption (P1, ADR-009 §4 violation, both stores;
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
     ADR-009 §3+§6 amendments recorded. fable-done in work/completed/keep/WO-0016-*/"
  - "WO-0018: def2501 (merge 7eaa262), VERIFIED, RESULT_SUMMARY_KEPT, non-gated; regime-adaptive
     spec per FINAL planning drop (d0b1728); divergences amended into the WO (missing LASE docs;
     .importlinter vs pyproject). fable-done in work/completed/keep/WO-0018-*/"
in-flight: WO-0022 Phase A — four critic subagents (spec-attacker, interleaving-attacker,
  test-critic, completeness-critic) launched against pinned tip f092ca7, H1-H11 inlined
  verbatim, fresh contexts. On completion: compile work/review/REV-0022/phase-a.md
  (findings → FINDING files + draft follow-up WOs; fix nothing). Phase B prep DONE:
  f092ca7 pinned into work/review/W3-codex-review-prompt.md — hand to human (T4).
awaiting:
  - T4: human runs Codex Phase B with work/review/W3-codex-review-prompt.md (SHA pinned).
    Note: the Sol/Codex seat already has the SOL-0001 addendum queued behind its in-flight
    review run.
  - WO-0024 approval (staged-order preemption fix — human-gated; blocks ADR-009 acceptance
    recommendation).
  - SOL-0001 deliverables (D1-D4) landing in work/collab/SOL-0001/; collab-protocol
    codification into .ai-os deferred until pilot returns (WO-0023 draft deleted at
    Ameen's request).
  - T5: ADR-009 Accepted + W3 merge — human only, after Phase B reconciliation.
anchor-divergences:
  - W3-README branch naming `feat/execution-envelope/wo-00XX` impossible in git (ref namespace);
    using `feat/execution-envelope-wo-00XX`.
  - WO-0020 committed directly on integration branch (hygiene slip, not rewritten).
  - WO-0018: LASE design docs 00/01/02/05 never present in this environment (amended into WO).
  - WO-0018: import contracts live in .importlinter, not pyproject.toml (amended into WO).
  - Planning drop (final) ADR-009 copy predates the ratified WO-0016 amendments — in-repo amended
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
  - WO-0024 approve/amend/reject (human-gated surface: engine cancel-path truth).
  - T4 Codex run timing (human executes).

## W3 sequencing status
0016 ✅ → 0018 ✅ → 0017 ✅ → 0019a ✅ → 0019 ✅ → 0020 ✅ → 0021 ✅ →
**0022 Phase A [critics running @ f092ca7]** → Phase B Codex (T4, human) → T5 ADR-009
Accepted + merge (human only).

## Gate/toolchain reference (this container)
ruff 0.15.20 · mypy 2.2.0 · pytest 9.1.1 · import-linter 2.13 — all == constraints.txt.
Gate: `ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`
(mypy invoked as `mypy app/` per CI; bare `mypy` has no default target in this repo).
Contracts now 6 (sellside-is-a-pure-policy added in WO-0018).
