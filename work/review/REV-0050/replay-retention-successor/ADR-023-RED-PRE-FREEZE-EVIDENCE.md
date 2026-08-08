# ADR-023 replacement RED pre-freeze evidence

Date: 2026-08-04

Authority base: `f528b5dd59a415413e010bb6015364d0094512c4`

Accepted ADR-023 SHA-256:
`898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`

Status: **CURRENT-WORKTREE ACCEPT — IMMUTABLE FREEZE AND EXACT-COMMIT REVIEW PENDING**

Production remains unchanged from the authority base. The replacement contract is intentionally
`STRUCTURALLY RED — SEMANTIC PATH NOT REACHED`; its failing production-facing controls are not
evidence that ADR-023 is implemented or operationally correct.

## Material review disposition

The pre-freeze reviews were limited to findings that could affect protection-state authenticity,
restart/replay correctness, bounded memory or work, deterministic CI, or execution-goal safety.
They found and closed these material test-contract classes:

- canonical private-import and direct SHA-256-digest feasibility;
- exact state-commitment signature, helper binding, part order, and direct retained-field sources;
- stale, forked, advancing, and current invalidation projection authority;
- repeated authenticated branch resets in bounded 10/100,000 histories;
- qualified, structured, conditional, unresolved, and imported annotation laundering;
- complete `ExecutionGoal` and `ProtectionTransition` constructor lifecycle closure;
- complete typed optional-cursor authenticity mutations; and
- exact fixed-cardinality state leaves, excluding `object`, `type`, `VenueRecoveryTransition`,
  receipt maps, and variable-cardinality containers.

The final materiality-scoped delta review returned **ACCEPT**, P0=0, P1=0, P2=0. It independently
reproduced six focused controls. Production implementation, the immutable exact-commit review, and
later GREEN evidence remain separate gates.

## Exact pre-freeze results

Replacement RED collection and classification:

```text
tests/execution_core/test_import_boundary.py: 25
tests/execution_core/test_protection.py: 444
tests/execution_core/test_protection_stateful.py: 35
total: 504
intentional failures: 410
passes: 94
errors: 0
skips: 0
```

JUnit:
`ADR-023-RED-pre-freeze-candidate-3.junit.xml`

JUnit SHA-256:
`659E20BFC25E28B2A83C1A0F04F6AC497F3F1D6D10D17E094579DB29D3B4EE55`

Preserved predecessor execution-core corpus:

```text
745 passed
failures: 0
errors: 0
skips: 0
```

Predecessor JUnit:
`ADR-023-predecessor-pre-freeze-candidate-3.junit.xml`

Predecessor JUnit SHA-256:
`999539B50789FEF6507D251A3E23E8F56A761F451E109814B54B28CAD6E6BF78`

Five parent-run source/oracle controls passed. Ruff check and changed-file format-check passed;
Python 3.11 AST parsing passed for all three files; `git diff --check`, the active-WO scope check,
and the application-diff-absence gate passed. Mypy passed over 86 application files. Install,
version (`v0.9.1`), ledger, PKL, and work-order disposition checks passed. All nine auxiliary
worktrees were verified clean using command-local `safe.directory` values; no global Git
configuration changed.

## Candidate file hashes

```text
F95F415B4AE61AA01A4E58FF80313A7A89F52AD98CEAFC5CC6F0F4CB006A0BD1  tests/execution_core/test_protection.py
1F0507A5267C3A032E82D93240B41F3DA36BF1C793A2418FE90F2968CD31CB61  tests/execution_core/test_protection_stateful.py
9E08A9031C7F67F1E86B714125C0EC66C98B862964D4892D2D680D5921DECE3A  tests/execution_core/test_import_boundary.py
```

## Boundary statement

No application file changed. No SQL/DDL, direct database work, broker or Alpaca activity, external
network activity, runtime wiring, M2 implementation, master merge, deletion, cleanup, push, or
credential discovery occurred. After evidence capture, staging was limited to the six authorized
RED-freeze files named by the candidate diff.

The next gate is to commit this exact RED/evidence set as an immutable candidate and obtain a fresh
independent exact-commit ACCEPT with zero unresolved P0/P1 before any production edit.
