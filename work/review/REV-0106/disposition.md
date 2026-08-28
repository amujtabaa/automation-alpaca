---
type: Review Disposition
rev_id: REV-0106
work_order_id: WO-0168d
status: OPEN
date: 2026-08-27
recorded_by: Codex implementation seat
---

# REV-0106 round-one disposition

## Decision

Accept the reviewer-owned `result.md` unchanged as the authoritative round-one `BLOCK` against
candidate `f20eddd4d060f7506bbbe563761bbf964731275f`, tree
`36f4b028927110cf318c0f2f74108f7f083f8177`. Its SHA-256 is
`05ae57f3533800a9d132719ff966ba095a537e28a7bb0f7939bc6a65b448d442` and its counts are
P0=1/P1=2/P2=0. All three findings reproduced without SQLite, DDL execution, or database creation.

## In-scope P1 root remediations

Commit `d22c236` resolves both P1 findings inside the existing work order:

1. `REV-0106-F2`: the direct-connection AST control resolves ordinary `import sqlite3 as ...`
   aliases and `from sqlite3 import connect` aliases. It also resolves ordinary gate aliases so
   legitimate gate-first code does not become a false positive. Negative and positive canaries
   pin each shape.
2. `REV-0106-F3`: justified token paths now carry exact per-token occurrence counts rather than
   whole-file exemptions. Adding a second SQLite occurrence to an already admitted production
   path fails closed. The focused boundary/kernel set passes 17 tests; Ruff check and format pass;
   the boundary plus gate remains 370 nonblank/non-comment SLOC, below the 400-SLOC budget.

These changes remain subject to the one permitted fresh remediation review round and are not
accepted merely because author checks pass.

## P0 root analysis and required authority

`REV-0106-F1` is valid. The fixture-side human accessor refuses while its flag is False, but the
application-side public `install_schema` boundary has no independent authorization check. Supplying
the known matching digest reaches connection inspection. Another fixture-only or scanner patch
would be a band-aid because the sensitive operation itself would remain callable.

The smallest root correction is to move the still-False authorization fact and expected identity
to `app/execution_core/persistence/schema.py`, make `install_schema` verify both before touching the
supplied connection, and retain `approved_schema_digest.py` as the pre-open convenience guard backed
by the same application-owned facts. Add a no-I/O stand-in test proving a direct installer call
with the known matching digest still refuses before connection access while authorization is
False. Preserve the DDL literal byte-for-byte and do not run the held suites.

That correction changes a human-gated application boundary and `app/**` is expressly forbidden by
WO-0168d's current authority. It therefore requires Ameen's explicit scope expansion before code
changes. If authorized, the bounded added paths are:

- `app/execution_core/persistence/schema.py` (authorization check only; no DDL-byte change),
- `tests/execution_core/approved_schema_digest.py`,
- `tests/execution_core/test_sqlite_boundary.py`,
- the four relocated `tests_gated/execution_core/test_persistence_*.py` call sites by static edit
  only if the installer signature changes,
- WO-0168d, ADR-026, the DDL gate record, ledger, and REV-0106 disposition/request addendum.

## Scope expansion authorized

On 2026-08-27 Ameen supplied the exact requested authority: "I authorize the bounded REV-0106-F1
remediation of the application-side schema installer and supporting gate tests/governance records.
The human authorization flag must be enforced before connection access. No DDL-byte change, held-
suite execution, database creation, migration, or later work-order implementation is authorized.
Obtain fresh exact-head review with zero open P0/P1 before proceeding to the separate DDL execution
gate." The authority is recorded in WO-0168d and Amendment 9 of the governing DDL gate.

The revised candidate must receive one fresh exact-head REV-0106 round-two review with zero open
P0/P1. The changed-DDL gate remains closed throughout; no held suite, DDL, or database execution is
authorized by this disposition.

## Round-two candidate

The authorized root remediation is frozen at commit
`a5c95ca271c99f79ecfd045468072274107f6ead`, tree
`fdbdbe0934a08e97d542945d28b937bdc67708ea`. `install_schema` now computes the actual digest,
requires the application-owned still-False human authorization and expected identity, checks the
caller digest, and only then may inspect its supplied connection. The fixture accessor imports the
same two application-owned facts. Its public signature and `__all__` remain unchanged.

Static extraction proves the `SCHEMA_DDL` remains 178,755 UTF-8 bytes with SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`; the new schema blob is
`ef332a0b97d28e0535ac53ea0e4d4e091991abad`, changed only because the gate now lives at the
sensitive boundary. Focused no-I/O tests pass 18; all ordinary `tests/execution_core` reached 100%
with exit 0; Ruff, mypy (95 app files), six import contracts, and governance/scope checks pass.
Broader repository and conformance suites remain NOT_RUN because they create databases forbidden by
the bounded authority. `request-r2.md` binds the one fresh final review round to this exact head.

[DONE] STATUS: VERIFIED
