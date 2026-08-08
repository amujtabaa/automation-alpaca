# WO-0148 ADR-023 immutable application acceptance review

## Exact candidate

- Parent: `4c420e1e9323bf881683ddc197758535b5638519`
- Candidate: `629ffaa3f9a93ce2cc44ba38197f2ed8428cc11d`
- Exact candidate paths:
  - `app/execution_core/__init__.py`
  - `app/execution_core/identity.py`
  - `app/execution_core/protection.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
  - `work/review/REV-0050/adr023-green-candidate/GREEN-EVIDENCE.md`

Review the immutable parent-to-candidate delta. The current tracked tree is at the candidate; all
untracked historical artifacts are excluded and must remain untouched.

## Governing authority and scope

Re-derive behavior from accepted ADR-020, ADR-021, ADR-022, amended ADR-023 R1, ratification, the
active WO, predecessor code, and the tests. Do not rely on author reasoning or the evidence file as
authority. This slice is pure, broker-neutral, deterministic, constant-cardinality, and unwired.

No database or SQL, broker or Alpaca, network, credentials, runtime wiring, persistence cutover,
M2 implementation, master merge, deletion, or cleanup operation is permitted. Write findings only
to this directory's `result.md`; do not edit application, tests, ADRs, PKL, ledger, WO, evidence, or
request.

## Required independent determination

Prioritize material behavior that can affect live-capital safety once a later authorized runtime
integrates this pure kernel:

1. Verify the five public functions and opaque state/projection boundaries are exact; no caller-
   supplied closure, formula-ready, baseline, waiting, or execution-eligibility authority is
   accepted.
2. Verify only canonical current execution and venue ownership advance economics; submitted/status
   facts cannot change quantity, flat requires complete closure/binding/reconciliation, late
   positive quantity restores sticky emergency protection, and every blocking effect suppresses a
   goal.
3. Verify hard-bail/activation/trail arithmetic, tick rounding, monotonicity, corroboration resets,
   precedence, waiting semantics, and SELL goal guard/urgency/residual/current-commitment binding.
4. Verify market authority is derived, generation/mode/scope/session bound, strict-coordinate and
   epoch ordered, exact-replay classified before conflict/stale, cursor-reserving before contextual
   eligibility, baseline/halt/invalidation/exhaustion safe, and constant-size at 19 parts/480 bytes.
5. Verify identity text/bytes/seal canonicality and every retained cursor/evidence/provenance input
   participates in authentication. Check coordinated mutations and restart/replay cases, not only
   single-field changes.
6. Verify the implementation contains no hidden I/O, time, randomness, mutable global state,
   variable-history container, history scan, silent eviction, dynamic dispatch, or broadened import
   capability, and remains within the exact allowed paths.

Use focused counterexamples and source tracing before broad repetition. Reproduce the 509-test
direct/stateful/import set and static gates as useful; run the 1,254-test full execution-core corpus
only if needed to resolve a material uncertainty. Treat author claims as claims. Any test that
cannot fail or any completion claim not reproducible is blocking under repository rules.

For each finding provide P0/P1/P2, file:line, concrete production/proof impact, a minimal
counterexample, and the smallest root correction. End with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or
`BLOCK`, exact P0/P1/P2 counts, evidence reproduced, and anything not verified. Acceptance requires
P0=0 and P1=0.
