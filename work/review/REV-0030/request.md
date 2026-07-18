---
type: Review Request
rev_id: REV-0030
title: WO-0109 REV-0029 round-3 correctness remediation
status: AWAITING_REVIEW
targets: [WO-0109, ADR-010, INV-081, INV-090]
human_gated_surfaces:
  - order submission and final claim
  - manual flatten
  - BUY cancellation
  - submit-recovery and event-log truth
commit_range: 7e59a9e..51dee57
created: 2026-07-18
---

## Your role

You are the independent review seat, deliberately different from the Codex implementer. Follow
`AGENTS.md` and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`. Re-derive the behavior from the
diff and current tests; do not rely on the implementer's reasoning or the in-process audits. Produce
findings only and do not push fixes. The operator authorization for these human-gated remediation
surfaces is recorded in WO-0109's “Seat model” section; it authorizes remediation, not merge.

Create `result.md` in this folder. Each finding must give `file:line`, why it matters, and what
resolves it. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, plus anything not verified.

## What you are reviewing

Run:

```powershell
git diff --stat 7e59a9e..51dee57
git diff 7e59a9e..51dee57
```

WO-0109 closes every BLOCK-worthy finding from `work/review/REV-0029/result-round2.md` in five
scoped commits:

1. `5b4e742` — stale-snapshot BUY cancellation uses store-atomic compare-and-swap; open BUY
   recoveries join the same-symbol execution-exposure projection used by flatten and final claim.
2. `1e14189` — recovery ingress validates immutable Order scope under the store lock/transaction;
   legacy mismatches remain visible through declared and referenced-Order SELL scope; honest sibling
   stage/final-claim schedules replace the inert round-2 fixture.
3. `3f85656` — symbol-only malformed lineage is diagnostic only and can never authorize a broker
   cancel; event-correlation and referenced-Order-owner keys are mutually exclusive pins.
4. `d12596d` — stream parity preserves causal/payload timestamps; T1.3 checks reachable executable
   producer/consumer AST sites rather than filenames or textual mentions.
5. `51dee57` — dual-store lifecycle backfill becomes linear; SQLite action selection preserves the
   old selector algebra through indexed arms, bind-limit chunking, dedupe, exclusion, and sequence
   order. No performance threshold changed.

## Start here

- Stale cancel and shared BUY exposure:
  `app/monitoring.py:250`, `app/monitoring.py:279`, `app/store/memory.py:2629`,
  `app/store/memory.py:3418`, `app/store/sqlite.py:3964`, `app/store/sqlite.py:4842`.
- Recovery ingress / legacy scope / sibling rails:
  `app/store/memory.py:3463`, `app/store/sqlite.py:4941`,
  `tests/test_wo0109_round3_remediation.py:100`,
  `tests/test_wo0109_round3_remediation.py:366`.
- Diagnostic scope versus cancel authority:
  `tests/test_wo0036_r2_hostile_closure.py:3608`,
  `tests/test_wo0036_r2_hostile_closure.py:3681`,
  `tests/test_wo0036_r2_hostile_closure.py:3737`.
- Comparator and executable-site gates:
  `tests/test_wo0036_r2_close_and_recovery_ownership.py:335`,
  `tests/test_wo0036_r2_close_and_recovery_ownership.py:360`,
  `tests/test_review_hardening_gates.py:266`, `tests/test_review_hardening_gates.py:298`,
  `tests/test_review_hardening_gates.py:328`.
- Scaling implementation and non-vacuous pins:
  `app/store/memory.py:231`, `app/store/sqlite.py:592`, `app/store/sqlite.py:1937`,
  `tests/test_wo0013_event_truth_writepath.py:189`,
  `tests/test_wo0036_r2_hostile_closure.py:3779`,
  `tests/test_wo0036_r2_hostile_closure.py:3962`,
  `tests/performance/r2_scaling_gate.py:321`.
- Contract text: `docs/INVARIANTS.md` INV-081 and INV-090; ADR-010 §3/§4;
  `pkl/process/review-hardening.md`; `pkl/architecture/testing-model.md`.

## Required review questions

1. Can a stale `CREATED` snapshot still terminalize a BUY that became `SUBMITTING`, or let a SELL
   be minted/claimed beside a BUY that may execute at the paper venue?
2. Can recovery-declared identity suppress the referenced Order's immutable symbol/side, at ingress
   or when projecting legacy rows? Are both store transactions truly atomic?
3. Does any symbol-only fact enter the cancellation target set rather than diagnostics only?
4. Can any comparator normalization still erase semantic event/payload time, or can a dead/import/
   comment-only producer/consumer satisfy T1.3?
5. Is SQLite's split selector exactly
   `parent OR ((event-owner OR order-owner) AND (event-symbol OR order-symbol))` when both selectors
   are present? Are exact-envelope, exclusion, dedupe, global sequence, and bind-limit behavior
   preserved without a global action-corpus walk?
6. For every claimed mutation pin, can the guarded branch actually be removed while the exact test
   turns red? Look specifically for fixtures satisfying multiple discovery keys accidentally.
7. Is every changed line traceable to WO-0109, with no architecture or paper-only invariant drift?

## Fresh probes for amended invariants

These are review probes, not reruns of the implementation's own pinning tests. Record the command or
harness and outcome in `result.md`.

- **INV-081 fresh probe:** on SQLite, persist a same-symbol BUY in `CANCEL_PENDING` plus an open
  `needs_review` BUY recovery, close/reopen the store, and request ordinary flatten. It must create no
  SELL. Resolve the recovery while the Order remains `CANCEL_PENDING`; flatten must still remain
  blocked by Order exposure. Only a broker-authoritative BUY terminal plus resolved recovery may
  release the symbol. Repeat the observable sequence on the memory store.
- **INV-090 fresh probe:** seed one malformed action whose event owner matches intent `I` and whose
  referenced Order symbol matches `AAPL`, while event symbol, Order owner, and parent all disagree;
  seed a newer symbol-only malformed action beside it. After SQLite restart (and on memory), the
  combined owner+symbol projection must include only the cross-key first action, the symbol
  diagnostic must see both, cancellation authority must never target the symbol-only child, and
  `active_sell_intent_for("AAPL")` must expose exactly the retained owner.

## Verification commands

```powershell
ruff check .
ruff format --check .
mypy app/
lint-imports
pytest -q
pytest -q tests/r2_conformance_oracle.py
pytest -q tests/test_r2_conformance_oracle_claude.py
pytest -q tests/test_review_hardening_gates.py
python -m tests.performance.r2_scaling_gate
pytest --cov=app --cov-branch
```

Implementer evidence: full native suite exit 0 in 317.5s; coverage 3,146 passed / 11 skipped /
1 expected xfail at 93.92% branch coverage; oracles 61 passed and 22 passed + 6 documented skips;
hardening 12 passed; three sequential unprofiled scaling runs were under both unchanged limits.
Treat these as claims to reproduce, not as a substitute for review.
