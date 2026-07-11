# W3 state — updated 2026-07-11T22:10Z, tip f0f75cb (feat/execution-envelope)
approved-agreement: W3 kickoff prompt (work/queue/W3-KICKOFF-PROMPT.md), pasted 2026-07-11
completed:
  - "WO-0016: 5ca48f2 (merge f0f75cb), VERIFIED, disposition RESULT_SUMMARY_KEPT+ADR_CREATED,
     T1 approved in-chat; ADR-009 §3+§6 amendments recorded (escape edges; activated/completed/
     cancelled events + additive envelope_id column). fable-done:
     work/completed/keep/WO-0016-envelope-entity-events-persistence/fable-done.md"
in-flight: WO-0018 (pure sell-side policy — non-gated, next per 0017∥0018 sequencing in one
  session: 0018 first, then post WO-0017 gate block and stop for T2)
awaiting: none (T1 cleared; F1 cleared — repo-wide ruff format landed as e53cb00)
anchor-divergences:
  - W3-README branch naming `feat/execution-envelope/wo-00XX` is impossible in git (ref
    namespace collision with the parent branch). Using `feat/execution-envelope-wo-00XX`.
deferred log (out-of-scope observations):
  - app/store/base.py abstract StateStore has NO envelope declarations (base.py outside WO-0016
    allowed paths). Envelope API is concrete-only on both stores, parity by tests. WO-0019 needs
    the interface seam — add abstract methods + relocate EnvelopeTransitionError there then.
  - Container toolchain: /root/.local/bin shims (ruff 0.15.8, wrong mypy/pytest venvs) shadowed
    the pinned closure; removed + `pip install -r requirements.txt -c constraints.txt` +
    `pip install --ignore-installed PyYAML`. A FRESH container must redo this before trusting
    gate output. Python here is 3.11 (CI covers 3.11+3.12; authoritative env is 3.12).
  - pytest's final summary line is suppressed in this container (exit code + [100%] used as
    evidence instead). Not investigated; cosmetic.
open decisions: []

## Decisions taken under the T1 delegation ("smart choice", Ameen 2026-07-11)
1. ADR-009 §3: pre-activation escape edges PENDING/APPROVED -> {CANCELLED, EXPIRED};
   pre-activation supersession stays illegal (cancel + create new instead).
2. ADR-009 §6: + envelope_activated/envelope_completed/envelope_cancelled (log must replay the
   machine); ExecutionEvent.envelope_id additive nullable, NO schema-version bump.
3. Overfill semantics: ACTIVE + fill>remaining -> record faithfully, floor remaining at 0,
   chain BREACHED. FROZEN fill -> decrement, never unfreeze; completion on resume. Late fill on
   terminal -> recorded + flagged, status unchanged. Fills before activation -> InvalidFillError.

## Baseline gate (tip e6baf1c, 2026-07-11) — historical
- ruff check GREEN · ruff format RED(119 pre-existing, FIXED by e53cb00) · mypy GREEN ·
  lint-imports GREEN · pytest GREEN (exit 0, 3 keyless skips)

## Anchor re-verification (Step 0.5, tip e6baf1c) — all VERIFIED
- plan_flatten_position app/store/core.py:982 (pre-format numbering) · ApprovalGate(ABC)
  app/approval/gate.py:46 · SELL_INTENT_TRANSITIONS app/transitions.py:30 · MarketSnapshot
  app/marketdata/service.py:25 · ENG-001 atomic exit-open app/monitoring.py:318-383

## Wave sequencing (W3-README)
0016 ✅ → (0017 gated-T2 ∥ 0018 ✅-next) → 0019 gated-T3 (tripwire: verify adapter replace/edit
call exists first, else NEEDS-INPUT) → 0020 → 0021 → 0022 Phase A critics (inline H1-H11
verbatim; fresh contexts; pinned SHA) → Phase B Codex handoff (STOP) → T5 ADR-009 Accepted +
merge (human, never ours).
