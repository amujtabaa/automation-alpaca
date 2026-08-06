# WO-0148 exact-candidate production functional-conformance review

Status: **INDEPENDENT PRODUCTION ACCEPTANCE REVIEW**

Exact candidate: `34eb7f4aeea96c60522c4a8ca1b4575de41ffa39`

Implementation predecessor: `486b2500e2767f4874b2188bd81af2c908036b57`

Activation review base: `d75806b1a79d1769db25ae962c0977cd9388a886`

Review this immutable candidate independently. Conversation and implementation-seat summaries are
orientation only. Re-derive the contract from current code, tests, the active work order, accepted
ADRs, and reproducible evidence.

## Required authority packet

Read:

1. `AGENTS.md` and the `CLAUDE.md` safety core;
2. `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`;
3. accepted ADR-020, ADR-021, ADR-022, and their ratification digest index;
4. `work/review/REV-0050/PRODUCTION-SUCCESSOR-REGATE.md`;
5. `work/review/REV-0050/PRODUCTION-MUTATION-EVIDENCE.md`; and
6. `work/review/REV-0050/PRODUCTION-ACCEPTANCE-EVIDENCE.md`.

If any summary conflicts with the exact candidate, the candidate plus accepted authority wins.

## Review objectives

1. Re-derive the complete WO-0148 normative contract and public surface. Confirm the slice remains
   pure, deterministic, broker-neutral, and unwired, with no operational authority or second
   transition path.
2. Re-evaluate the late P1 family from first principles. Slow audit reconstruction must not accept
   coordinated replacement of a per-scope execution snapshot and protection cursor merely because
   those two derived indexes agree. Confirm the independently retained ordered transition history,
   per-scope predecessor chain, terminal cursor/snapshot pins, and sequence commitment form one
   complete owning rule.
3. Confirm every non-genesis transition proof binds its predecessor cursor to the same predecessor
   execution commitment and checkpoint, and confirm protection reduction returns `STALE` across an
   advancing predecessor execution discontinuity.
4. Trace multi-scope account cleanup, registry catch-up, unresolved non-advancing reconciliation,
   exact replay, hydration, projection, and later healthy advance. Look for duplicated truth,
   partial immutable publication, acceptance of caller-shaped material, or a path that silently
   changes the protection predecessor.
5. Review the narrow `authority.py` predecessor-interface amendment and prove that admission,
   mode/kill/fence, budget, grant, final claim, manual-flatten decisions, and authority-state
   mutation did not change outside the authorized tuple plumbing.
6. Evaluate the new 35-case coverage-strength matrix as behavioral evidence. Confirm its cases
   reach meaningful provenance/reconciliation rules, its named mutation can fail for the intended
   reason, and the 93% result was not obtained through production exclusions or test-only
   production paths.
7. Reconcile every changed line to an allowed path and accepted requirement. Confirm no accepted
   ADR body, runtime/persistence/broker/configuration surface, or closeout-only status file changed.
8. Perform an independent disproof pass with focused counterexamples. Do not accept because the
   implementation seat reports green evidence; attempt to contradict each material acceptance
   claim and remove any provisional finding that cannot be supported.

No formal `INV-*` entry was added or amended by this work order. The new probes are work-order
contract controls, not changes to the global invariant registry.

## Minimum fresh evidence

- Verify `HEAD` is exactly the candidate SHA and the activation-base range passes
  `.ai-os/scripts/check_work_order_scope.py`.
- Reproduce the 35 coverage-strength controls and the directly relevant transition-chain,
  protection, stateful, and import/public-boundary controls. Expand to predecessor/R2/execution-core
  tests in proportion to any concern.
- Reproduce Ruff, changed-file format, mypy, import contracts, Python 3.11 grammar, and
  `git diff --check` as needed to support the verdict.
- Independently parse or reproduce the final JUnit and raw coverage claims. Local raw artifacts are
  preserved under `work/review/REV-0050/evidence/` but are intentionally not committed; their hashes
  are recorded in `PRODUCTION-ACCEPTANCE-EVIDENCE.md`. Do not treat a hash match alone as proof of
  functional conformance.
- State anything not verified. Actual Python 3.11 and 3.12 execution remains the post-closeout
  exact-head CI gate and must not be reported as locally proved.

## Boundaries and output contract

This is a findings-only review seat. Do not edit production, tests, the work order, this request,
accepted authority, or implementation evidence. Do not commit, push, merge, clean, delete, inspect
credentials, call Alpaca or another external service, add runtime wiring, or make a persistent
application-database change. Existing mock/disposable test fixtures may run only under the recorded
WO authority.

Write only the durable review result to `work/review/REV-0050/result.md`. For every finding provide
priority, exact location, requirement, reproduced or static evidence, concrete impact, and the
smallest complete resolution. End with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

WO-0148 may proceed to closeout only if this exact candidate receives `ACCEPT` with P0=0/P1=0.

