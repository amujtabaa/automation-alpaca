# W3 state — updated 2026-07-11T20:45Z, tip e6baf1c
approved-agreement: W3 kickoff prompt (work/queue/W3-KICKOFF-PROMPT.md), pasted 2026-07-11
completed: []
in-flight: WO-0016 — gate block posted, awaiting T1 approval (schema migration, gated surface)
awaiting: T1 (WO-0016 gate approval) + batched decision on pre-existing `ruff format --check` debt
anchor-divergences: []
deferred log (out-of-scope observations):
  - Pre-existing repo-wide `ruff format --check .` failure: 119 files unformatted at inherited
    tip 6595bba under the PINNED ruff 0.15.20 (constraints.txt). CI (ci.yml) enforces only
    `ruff check .`, never `ruff format --check`, so this debt predates W3 and is invisible to CI.
    Affects every WO's Required-commands gate verbatim. Decision needed (batched with T1):
    (a) one-time `ruff format .` commit on feat/execution-envelope before WO-0016, or
    (b) scope format --check to files each WO touches. Recommendation: (a).
  - Container toolchain shipped shadowing uv-tool binaries in /root/.local/bin (ruff 0.15.8,
    mypy/pytest in isolated venvs). Removed shims; installed pinned closure per
    `pip install -r requirements.txt -c constraints.txt`. Session-local fix — a fresh container
    must redo this before trusting gate output.
  - Environment python is 3.11 (stack pin says 3.12; CI matrix covers both — acceptable).
open decisions:
  - Branch naming: harness designates push branch `claude/new-session-gu0z6y`; kickoff/W3-README
    specify `feat/execution-envelope`. Proceeding with feat/execution-envelope per kickoff
    (explicit human authorization); will fall back to the designated name only if the remote
    rejects the push, and will say so.

## Baseline gate (tip e6baf1c, 2026-07-11)
- ruff check .          GREEN
- ruff format --check . RED (119 files, pre-existing — see deferred log)
- mypy app/             GREEN (mypy 2.2.0 == constraints pin, 54 files)
- lint-imports          GREEN (5 contracts kept, 0 broken)
- pytest -q             GREEN (exit 0, [100%], 3 skips = keyless Alpaca integration)

## Anchor re-verification (Step 0.5, tip e6baf1c)
- plan_flatten_position        app/store/core.py:982            VERIFIED
- approval gate ABC            app/approval/gate.py:46          VERIFIED (ApprovalGate(ABC))
- SELL_INTENT_TRANSITIONS      app/transitions.py:30            VERIFIED
- MarketSnapshot shape         app/marketdata/service.py:25     VERIFIED
- ENG-001 atomic exit-open     app/monitoring.py:318-383        VERIFIED
