# WO-0148 ADR-023 GREEN candidate evidence

Evidence parent: `4c420e1e9323bf881683ddc197758535b5638519`

This is pre-freeze author-side evidence for the pure, unwired WO-0148 application candidate. It is
not independent acceptance and does not close the work order.

## Candidate scope and file hashes

Only the three authorized application files differ from the evidence parent:

| Path | SHA-256 |
|---|---|
| `app/execution_core/__init__.py` | `7558097911F4D167243A23C00C898827A8DE1B6163A95A072BC00DE5880FE2BC` |
| `app/execution_core/identity.py` | `F824624DADAA651409F2C1DA8B5776B9C28A633DFE3649DE7C47B90A6D1BF2C8` |
| `app/execution_core/protection.py` | `6568C75F933248D3BF26293D2AA85909E7474B0FAD10AD328FFCE5790BE0B34D` |

Application delta: 1,271 insertions and 671 deletions. It replaces the obsolete receipt-map market
path with the accepted five-function, constant-cardinality ADR-023 reducer surface and exports the
two required market identity/mode types.

## Functional evidence

- Exact direct/stateful/import set: **509/509 passed** in 112.3 seconds.
- Complete `tests/execution_core` corpus: **1,254/1,254 passed** in 316.8 seconds.
- The full protection file alone passed **447/447** after the coordinated-identity control was
  added; stateful protection is 35 tests and import-boundary is 27 tests.
- The accepted proof-isolation successor is
  `b7ae0d7db900557d54784ede2a27a7df65be0ae4`; independent exact-delta review returned
  `ACCEPT`, P0=0/P1=0/P2=0.

The candidate keeps the authenticated market cursor at exactly 19 parts/480 bytes, retains one
exact last eligible primary for the next maximum-step comparison while committing only its
canonical digest, derives occurrence identity from immutable occurrence inputs, reserves admitted
strict coordinates before contextual eligibility, and keeps replay/conflict/baseline/exhaustion
classification constant-size. Projection, market, and invalidation transitions remain separate.

A separate functional pre-flight reproduced a coordinated identity inconsistency that could turn
an exact replay into a false coordinate conflict. The root correction centralizes one identity-
owned invariant requiring exact text, its exact 32-byte decoding, and the corresponding seal.
Direct text-plus-seal, bytes-plus-seal, and end-to-end replay controls now fail closed.

## Static, scope, and repository evidence

- `ruff check .`: pass.
- Ruff format check for all three candidate application files: pass.
- `mypy app/`: pass, 86 source files.
- Import Linter: pass, 122 files / 621 dependencies / 6 contracts kept / 0 broken.
- Python 3.11 grammar and used-AST compatibility are exercised by the accepted protection
  contract and passed in the 509-test set.
- `git diff --check`: pass.
- Activation-base work-order scope: `SCOPE CHECK PASSED`.
- AI Project OS install, version (`v0.9.1`), ledger, and PKL checks: pass.

No database or SQL, broker or Alpaca, network, credential, runtime wiring, persistence cutover, M2
implementation, master merge, deletion, or cleanup operation was used. Preserved untracked
artifacts were not changed or treated as evidence.

## Remaining gate

Freeze the exact application/evidence candidate, then obtain one independent exact-candidate
production review with zero unresolved P0/P1. Exact-head Python 3.11/3.12 CI and final evidence/
closeout reconciliation remain later gates.
