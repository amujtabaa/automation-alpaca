# W3 state — updated 2026-07-12T01:30Z, tip ce40f90 (feat/execution-envelope)
approved-agreement: W3 kickoff prompt (work/queue/W3-KICKOFF-PROMPT.md, FINAL drop version), pasted 2026-07-11
completed:
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
in-flight: WO-0019 — BLOCKED at the tripwire: NO adapter replace/edit seam exists (ABC +
  all 3 concretes checked; SDK has replace_order_by_id). NEEDS-INPUT posted in-chat with
  work/queue/WO-0019a-broker-adapter-replace-seam.md drafted for approval (option a,
  recommended) vs cancel+resubmit descope (option b). 0020/0021 wait behind 0019 per
  W3-README sequencing.
awaiting: T3a — human decision on the WO-0019 tripwire (approve WO-0019a / choose descope /
  other)
anchor-divergences:
  - W3-README branch naming `feat/execution-envelope/wo-00XX` impossible in git (ref namespace);
    using `feat/execution-envelope-wo-00XX`.
  - WO-0018: LASE design docs 00/01/02/05 never present in this environment (amended into WO).
  - WO-0018: import contracts live in .importlinter, not pyproject.toml (amended into WO).
  - Planning drop (final) ADR-009 copy predates the ratified WO-0016 amendments — in-repo amended
    ADR kept authoritative (drop NOT copied over it), noted in d0b1728's message.
deferred log (out-of-scope observations):
  - app/store/base.py abstract StateStore lacks envelope API declarations (outside WO-0016 scope);
    WO-0019 should add them + relocate EnvelopeTransitionError from store/core.py.
  - models.py trail_distance_min/max docstrings say "trail distance"; WO-0018(final) defines them
    as ATR MULTIPLES — one-line docstring cleanup for a later WO (models.py forbidden in 0018).
  - compute_working_stop is O(n²) in bars (per-prefix indicator recompute) — fine at tick scale,
    revisit in W4 harness.
  - Container toolchain: /root/.local/bin shims shadowed pinned tools; removed + installed via
    constraints.txt. Fresh containers must redo. Python 3.11 here (authoritative env is 3.12).
  - pytest final summary line suppressed in this container; exit code + [100%] used as evidence.
open decisions: []

## W3 sequencing status
0016 ✅ → 0018 ✅ → 0017 ✅ → **0019 [BLOCKED: tripwire NEEDS-INPUT → T3a decision]** → 0020 → 0021 →
0022 Phase A critics (inline H1-H11 verbatim, fresh contexts, pinned SHA) → Phase B Codex (STOP)
→ T5 ADR-009 Accepted + merge (human only).

## Gate/toolchain reference (this container)
ruff 0.15.20 · mypy 2.2.0 · pytest 9.1.1 · import-linter 2.13 — all == constraints.txt.
Gate: `ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`
(mypy invoked as `mypy app/` per CI; bare `mypy` has no default target in this repo).
Contracts now 6 (sellside-is-a-pure-policy added in WO-0018).
