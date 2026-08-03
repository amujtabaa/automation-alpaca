# WO-0148 eighth RED independent-review disposition

Reviewed candidate: `7beda3f61e4d44f035143e883d7efa35a424f661`
Reviewer artifact: `RED-EIGHTH-RESULT.md`
Reviewer verdict: **BLOCK — P0: 0, P1: 2**

The implementation seat accepts both findings. The reviewer-owned result is preserved unchanged.
Production remained absent and barred throughout review and remediation.

## P1-1 — restart replay could retain negative evidence authority

**Disposition: ACCEPTED AND FIXED.**

The duplicate/restart history now requires the changed-delivery-context replay to return
`EXACT_REPLAY`, preserve the complete prior state and commitment, and emit neither goal nor alert.
It then branches an otherwise-valid advancing occurrence whose evaluation time is later than the
original evidence but earlier than the replay delivery context. That successor must still complete
hard-bail corroboration, so a replay-updated watermark is a failure-capable mutant.

## P1-2 — no-I/O gate permitted direct runtime output

**Disposition: ACCEPTED AND FIXED.**

The static contract now has two complementary layers. A package-wide effect detector rejects
effectful builtins, forbidden modules, imported aliases, dynamic call targets, and stream
capabilities. A protection-specific positive capability model accepts only exact builtin, local,
imported, attribute-call, decorator, base-class, and callback bindings. Every allowed import must
match an exact top-level manifest; module imports, nested or conditional imports, duplicate aliases,
rebinding, mutable or dynamic attribute access, unauthenticated callbacks, implicit protocol
imports, and dynamic type construction are rejected.

Failure-capable mutants cover direct and laundered output, callback donation, fake approved roots,
arbitrary relative callables and iterables, conditional alias replacement, relative module imports,
and dynamic class construction. A positive production-shaped skeleton remains accepted. Runtime
stdout/stderr capture around every public protection entry point is an independent complementary
tripwire, not the basis of the static proof.

## Fresh remediation evidence

- Complete focus collects 284 tests: 266 deterministic protection, 4 stateful, and 14
  import-boundary tests.
- Exact RED execution yields 228 expected failures and 56 passes: 225 failures are caused solely by
  deliberate absence of `app.execution_core.protection`, and 3 are the required inventory/AST/public
  export deltas. File split is 221/45, 3/1, and 4/10. No oracle helper fails.
- The structural capability meta-oracle rejects all output, binding-provenance, import-provenance,
  implicit-protocol, callback, and dynamic-construction mutants while accepting the positive
  production-shaped control.
- All eight current execution-core source files produce zero package effect-call violations.
- Ruff check and format-check pass for all three RED files; Python 3.11 grammar parsing, diff check,
  activation-base scope check, and the production-absence check pass.
- The independent eighth review reproduced 698/698 predecessor execution-core tests. The current
  remediation changes only the three deliberate RED files excluded from that preservation corpus.
- Iterative hostile re-review found and drove closure of five transitive capability subcases. Its
  final review of the current worktree reports **ACCEPT**, with zero P0 and zero P1 findings.

That worktree verdict is a pre-freeze control, not exact-commit acceptance. A ninth immutable RED
candidate and a fresh independent zero-P0/P1 review of that exact commit are still required before
production implementation may begin.
